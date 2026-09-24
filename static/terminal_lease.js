(function(){
  function renew(){
    fetch('/terminal-heartbeat',{
      method:'POST',credentials:'same-origin',cache:'no-store'
    }).catch(function(){});
  }
  window.setInterval(renew,45000);
})();
