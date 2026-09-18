V23.75 — EMAIL VOTING STREAM OPENING REPORTS

The voting-stream opening report now has an Email Opening Report button beside
Print A4 Report.

- The officer enters the recipient email address.
- The system creates a formatted A4 PDF containing the ODM header, stream
  opening details, stored opening GPS, zero-vote certification, candidate-agent
  signature tables and election-official signature lines.
- The PDF is attached to the email using the same Render SMTP settings already
  used by closing tally reports.
- The endpoint verifies that the device is assigned to the requested stream;
  a user cannot email an unrelated stream's opening report.

Deploy this package to the Voting Simulation System service only. No results
dashboard deployment is required for this change.
