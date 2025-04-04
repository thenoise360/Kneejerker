// analytics.js

// ---- 1. Init Mixpanel ----
(function(f,b){
    if(!b.__SV){
      var a,e,i,g;
      window.mixpanel=b;
      b._i=[];
      b.init=function(a,e,d){
        function f(b,h){
          var a=h.split(".");
          2==a.length&&(b=b[a[0]],h=a[1]);
          b[h]=function(){
            b.push([h].concat(Array.prototype.slice.call(arguments,0)))
          }
        }
        var c=b;
        "undefined"!==typeof d?c=b[d]=[]:d="mixpanel";
        c.people=c.people||[];
        c.toString=function(b){
          var a="mixpanel";
          "mixpanel"!==d&&(a+="."+d);
          return b||a
        };
        c.people.toString=function(){
          return c.toString(1)+".people"
        };
        i="disable time_event track track_pageview track_links track_forms register register_once alias unregister identify name_tag set_config reset people.set people.set_once people.unset people.increment people.append people.union people.track_charge people.clear_charges people.delete_user".split(" ");
        for(g=0;g<i.length;g++)f(c,i[g]);
        b._i.push([a,e,d])
      };
      b.__SV=1.2;
      a=f.createElement("script");
      a.type="text/javascript";
      a.async=!0;
      a.src="https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js";
      e=f.getElementsByTagName("script")[0];
      e.parentNode.insertBefore(a,e)
    }
  })(document,window.mixpanel||[]);
  
  // Init with your token
  mixpanel.init("8bdc155b6f5d87b8863f7477afb96306");
  
  // ---- 2. Global event: track all page loads ----
  mixpanel.track("Page Loaded", {
    path: window.location.pathname,
    title: document.title
  });
  
  // ---- 3. Optional: helpers you can call from anywhere ----
  
  export function trackPlayerClick(playerId, playerName) {
    mixpanel.track("Player Clicked", {
      id: playerId,
      name: playerName
    });
  }
  
  export function identifyUser(userId, traits = {}) {
    mixpanel.identify(userId);
    mixpanel.people.set(traits);
  }
  
  
  export function trackPlayerSummary(playerId, playerName) {
      mixpanel.track("Player Summary Viewed", {
      id: playerId,
      name: playerName
      });
  }

  export function trackComparison(id1, id2, name1, name2) {
    mixpanel.track('Player Comparison', {
        player1_id: id1,
        player1_name: name1,
        player2_id: id2,
        player2_name: name2
    });
  }

  
  export function trackCarousel(position, playerName) {
    mixpanel.track("Top Player Carousel Viewed", {
      position: position,
      player: playerName
    });
  }
  
  export function trackTeamOptimization(sliders) {
    mixpanel.track("Team Optimized", {
      pointsWeight: sliders[0],
      formWeight: sliders[1],
      minutesWeight: sliders[2]
    });
  }