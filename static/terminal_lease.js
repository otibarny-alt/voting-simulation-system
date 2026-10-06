(function(){
  function renew(){
    fetch('/terminal-heartbeat',{
      method:'POST',credentials:'same-origin',cache:'no-store'
    }).then(function(response){return response.json().catch(function(){return {};});})
      .then(function(data){if(data.stream_reopened)window.location.reload();})
      .catch(function(){});
  }
  renew();
  window.setInterval(renew,45000);
})();
