async function emailStoredReport(button){
  const recipient=window.prompt('Enter the recipient email address:','');
  if(recipient===null)return;
  const email=recipient.trim();
  if(!email)return window.alert('Enter a recipient email address.');
  const original=button.textContent;
  button.disabled=true;
  button.textContent='Sending…';
  try{
    const response=await fetch(button.dataset.endpoint,{
      method:'POST',credentials:'same-origin',cache:'no-store',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({email})
    });
    const data=await response.json().catch(()=>({error:'The server returned an unreadable response.'}));
    window.alert(data.message||data.error||(response.ok?'Report emailed successfully.':'Unable to email report.'));
  }catch(error){
    window.alert('Unable to contact the email service. Please try again.');
  }finally{
    button.disabled=false;
    button.textContent=original;
  }
}
