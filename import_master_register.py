#!/usr/bin/env python3
import argparse
import csv
import os
import re
import sys
import uuid

from master_register import connect, ensure_schema


ALIASES = {
    "national_id": ("national_id_no", "national_id", "member_id", "id_number"),
    "serial_no": ("serial_no", "serial_number", "serial"),
    "party_membership_number": ("odm_membership_no", "party_membership_number", "membership_no"),
    "first_name": ("first_name",), "middle_name": ("middle_name", "other_names"),
    "surname": ("surname", "last_name"), "full_name": ("full_name", "name_in_full"),
    "phone": ("phone_no", "phone", "phone_number"), "gender": ("gender", "sex"),
    "date_of_birth": ("dob", "date_of_birth"), "county": ("county",),
    "constituency": ("constituency",), "ward": ("ward",),
    "polling_station": ("poll_station", "polling_station", "polling_station_name"),
    "polling_station_code": ("poll_station_code", "polling_station_code"),
    "id_photo_ref": ("member_id_photo", "id_photo", "id_photo_url"),
    "passport_photo_ref": ("member_passport_photo", "passport_photo", "passport_photo_url"),
    "source_submission_id": ("_id", "submission_id", "kobo_submission_id"),
    "source_updated_at": ("_submission_time", "updated_at", "submission_time"),
}
COLUMNS = tuple(ALIASES)


def normalized_header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def value(row, name):
    for alias in ALIASES[name]:
        found = row.get(normalized_header(alias))
        if found not in (None, ""):
            return str(found).strip()
    return ""


def clean_row(raw):
    row = {normalized_header(k): ("" if v is None else str(v).strip()) for k, v in raw.items()}
    result = {name: value(row, name) for name in COLUMNS}
    result["national_id"] = re.sub(r"\D", "", result["national_id"])
    if not result["full_name"]:
        result["full_name"] = " ".join(x for x in (result["first_name"], result["middle_name"], result["surname"]) if x)
    return result


def stage(path, mode, encoding, resume_batch=None):
    ensure_schema(); batch_id = uuid.UUID(resume_batch) if resume_batch else uuid.uuid4()
    with connect() as conn:
        with conn.cursor() as cur:
            if resume_batch:
                cur.execute("SELECT * FROM voter_register_import_batches WHERE batch_id=%s", (batch_id,)); batch = cur.fetchone()
                if not batch or batch["status"] != "STAGING":
                    raise RuntimeError("Only an existing STAGING batch can be resumed.")
                if batch["filename"] != os.path.basename(path):
                    raise RuntimeError("The resume file name does not match the original batch file.")
                mode = batch["mode"]
                cur.execute("SELECT COALESCE(MAX(row_number),0) AS n FROM voter_register_stage WHERE batch_id=%s", (batch_id,)); staged = int(cur.fetchone()["n"] or 0)
            else:
                cur.execute("INSERT INTO voter_register_import_batches(batch_id, filename, mode) VALUES (%s,%s,%s)", (batch_id, os.path.basename(path), mode))
                staged = 0
        conn.commit()
        with open(path, "r", encoding=encoding, errors="replace", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise RuntimeError("The CSV has no header row.")
            for _ in range(staged):
                try: next(reader)
                except StopIteration: break
            while True:
                rows = []
                try:
                    for _ in range(100000):
                        raw = next(reader); staged += 1; item = clean_row(raw)
                        error = ""
                        if not item["national_id"]: error = "Missing National ID"
                        if not item["serial_no"]: error = (error + "; " if error else "") + "Missing serial number"
                        rows.append((batch_id, staged, *(item[c] for c in COLUMNS), error))
                except StopIteration:
                    pass
                if rows:
                    fields = "batch_id,row_number," + ",".join(COLUMNS) + ",validation_error"
                    with conn.cursor() as cur:
                        with cur.copy(f"COPY voter_register_stage ({fields}) FROM STDIN") as copy:
                            for row in rows: copy.write_row(row)
                    conn.commit(); print(f"Staged {staged:,} rows", flush=True)
                if len(rows) < 100000: break
        with conn.cursor() as cur:
            cur.execute("""WITH ranked AS (
                             SELECT row_number,
                               COUNT(*) OVER (PARTITION BY LOWER(serial_no)) AS serial_count,
                               COUNT(*) OVER (PARTITION BY national_id) AS national_count,
                               CASE WHEN NULLIF(party_membership_number,'') IS NULL THEN 1
                                    ELSE COUNT(*) OVER (PARTITION BY LOWER(party_membership_number)) END AS membership_count
                             FROM voter_register_stage WHERE batch_id=%s
                           ), duplicates AS (
                             SELECT row_number FROM ranked
                             WHERE serial_count>1 OR national_count>1 OR membership_count>1
                           )
                           UPDATE voter_register_stage s SET validation_error=CONCAT_WS('; ',NULLIF(validation_error,''),'Duplicate serial number or National ID in import')
                           FROM duplicates d WHERE s.batch_id=%s AND s.row_number=d.row_number""", (batch_id, batch_id))
            cur.execute("""SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE COALESCE(validation_error,'')='') AS valid,
                           COUNT(*) FILTER (WHERE COALESCE(validation_error,'')<>'') AS rejected
                           FROM voter_register_stage WHERE batch_id=%s""", (batch_id,))
            counts = cur.fetchone()
            cur.execute("""UPDATE voter_register_import_batches SET status='STAGED',staged_rows=%s,valid_rows=%s,rejected_rows=%s,staged_at=NOW()
                           WHERE batch_id=%s""", (counts["total"], counts["valid"], counts["rejected"], batch_id))
        conn.commit()
    print(f"Batch {batch_id} staged: {counts['valid']:,} valid; {counts['rejected']:,} rejected.")
    return batch_id


def promote(batch_id, allow_rejections=False):
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM voter_register_import_batches WHERE batch_id=%s FOR UPDATE", (batch_id,)); batch = cur.fetchone()
            if not batch: raise RuntimeError("Import batch was not found.")
            if batch["status"] == "PROMOTED": raise RuntimeError("This batch has already been promoted.")
            cur.execute("""UPDATE voter_register_stage s SET validation_error=CONCAT_WS('; ',NULLIF(s.validation_error,''),'Conflicts with an existing voter identity')
                           WHERE s.batch_id=%s AND COALESCE(s.validation_error,'')='' AND EXISTS (
                             SELECT 1 FROM master_voters v WHERE
                             (LOWER(v.serial_no)=LOWER(s.serial_no) AND v.national_id<>s.national_id) OR
                             (v.national_id=s.national_id AND LOWER(v.serial_no)<>LOWER(s.serial_no)) OR
                             (NULLIF(s.party_membership_number,'') IS NOT NULL AND LOWER(v.party_membership_number)=LOWER(s.party_membership_number) AND v.national_id<>s.national_id))""", (batch_id,))
            cur.execute("""SELECT COUNT(*) FILTER (WHERE COALESCE(validation_error,'')='') AS valid,
                           COUNT(*) FILTER (WHERE COALESCE(validation_error,'')<>'') AS rejected
                           FROM voter_register_stage WHERE batch_id=%s""", (batch_id,)); review = cur.fetchone()
            if int(review["valid"] or 0) < 1:
                raise RuntimeError("Promotion blocked because the batch contains no valid voters.")
            if int(review["rejected"] or 0) and not allow_rejections:
                raise RuntimeError("Promotion blocked because rejected rows exist. Export and correct them, or rerun promote with --allow-rejections after explicit review.")
            if batch["mode"] == "replace": cur.execute("UPDATE master_voters SET active=FALSE,updated_at=NOW()")
            cur.execute("""INSERT INTO master_voters (national_id,serial_no,party_membership_number,first_name,middle_name,surname,full_name,phone,gender,date_of_birth,county,constituency,ward,polling_station,polling_station_code,id_photo_ref,passport_photo_ref,source_submission_id,source_updated_at,import_batch_id,active,updated_at)
                           SELECT national_id,serial_no,party_membership_number,first_name,middle_name,surname,full_name,phone,gender,date_of_birth,county,constituency,ward,polling_station,polling_station_code,id_photo_ref,passport_photo_ref,source_submission_id,source_updated_at,batch_id,TRUE,NOW()
                           FROM voter_register_stage WHERE batch_id=%s AND COALESCE(validation_error,'')=''
                           ON CONFLICT (national_id) DO UPDATE SET serial_no=EXCLUDED.serial_no,party_membership_number=EXCLUDED.party_membership_number,first_name=EXCLUDED.first_name,middle_name=EXCLUDED.middle_name,surname=EXCLUDED.surname,full_name=EXCLUDED.full_name,phone=EXCLUDED.phone,gender=EXCLUDED.gender,date_of_birth=EXCLUDED.date_of_birth,county=EXCLUDED.county,constituency=EXCLUDED.constituency,ward=EXCLUDED.ward,polling_station=EXCLUDED.polling_station,polling_station_code=EXCLUDED.polling_station_code,id_photo_ref=EXCLUDED.id_photo_ref,passport_photo_ref=EXCLUDED.passport_photo_ref,source_submission_id=EXCLUDED.source_submission_id,source_updated_at=EXCLUDED.source_updated_at,import_batch_id=EXCLUDED.import_batch_id,active=TRUE,updated_at=NOW()""", (batch_id,))
            promoted = cur.rowcount
            cur.execute("SELECT COUNT(*) AS n FROM voter_register_stage WHERE batch_id=%s AND COALESCE(validation_error,'')<>''", (batch_id,)); rejected = cur.fetchone()["n"]
            cur.execute("UPDATE voter_register_import_batches SET status='PROMOTED',promoted_rows=%s,rejected_rows=%s,promoted_at=NOW() WHERE batch_id=%s", (promoted, rejected, batch_id))
        conn.commit()
    print(f"Batch {batch_id} promoted: {promoted:,} rows; {rejected:,} rejected.")


def export_errors(batch_id, output_path):
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT row_number,national_id,serial_no,party_membership_number,full_name,
                           county,constituency,ward,polling_station,validation_error
                           FROM voter_register_stage WHERE batch_id=%s AND COALESCE(validation_error,'')<>''
                           ORDER BY row_number""", (batch_id,))
            rows = cur.fetchall()
    fields = ("row_number","national_id","serial_no","party_membership_number","full_name","county","constituency","ward","polling_station","validation_error")
    with open(output_path, "w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows):,} rejected rows to {output_path}")


def show_status():
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT batch_id,filename,mode,status,staged_rows,valid_rows,rejected_rows,promoted_rows,started_at,staged_at,promoted_at
                           FROM voter_register_import_batches ORDER BY started_at DESC LIMIT 20""")
            rows = cur.fetchall()
    for row in rows:
        print(" | ".join(str(row.get(key) or "") for key in ("batch_id","status","mode","staged_rows","valid_rows","rejected_rows","promoted_rows","filename")))


def main():
    parser = argparse.ArgumentParser(description="Stage or promote a large membership register without loading it into memory.")
    sub = parser.add_subparsers(dest="command", required=True)
    stage_cmd = sub.add_parser("stage"); stage_cmd.add_argument("csv_path"); stage_cmd.add_argument("--mode", choices=("merge","replace"), default="replace"); stage_cmd.add_argument("--encoding", default="utf-8-sig"); stage_cmd.add_argument("--resume-batch")
    promote_cmd = sub.add_parser("promote"); promote_cmd.add_argument("batch_id"); promote_cmd.add_argument("--allow-rejections", action="store_true")
    errors_cmd = sub.add_parser("errors"); errors_cmd.add_argument("batch_id"); errors_cmd.add_argument("output_csv")
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "stage": stage(args.csv_path, args.mode, args.encoding, args.resume_batch)
    elif args.command == "promote": promote(uuid.UUID(args.batch_id), args.allow_rejections)
    elif args.command == "errors": export_errors(uuid.UUID(args.batch_id), args.output_csv)
    else: show_status()


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr); raise SystemExit(1)
