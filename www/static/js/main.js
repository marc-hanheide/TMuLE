var hostname = location.hostname;
console.log(hostname);


function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function executeFunctionByName(functionName, context /*, args */) {
  var args = [].slice.call(arguments).splice(2);
  var namespaces = functionName.split(".");
  var func = namespaces.pop();
  for(var i = 0; i < namespaces.length; i++) {
    context = context[namespaces[i]];
  }
  return context[func].apply(context, args);
}


function send(data) {
  //data['_location'] = location;
  data['_id'] = uuidv4();
  var buffer=JSON.stringify(data);
  socket.send(buffer);
}

function _ping(payload) {
  console.log('ping ' + JSON.stringify(payload, null, 2));
  return {'ping_result': true};
}

function _update_html(payload) {
  console.log('html update for id=' + payload['id'])
  $('#'+payload['id']).html(payload['html'])
}


function init() {
  var host_name = window.location.hostname;
  socket = new ReconnectingWebSocket("ws://" + host_name + ":9998");
  socket.binaryType = "arraybuffer";

  socket.onopen = function () {
    console.log("Connected!");
    check();

  };

  socket.onmessage = function (e) {
    if (typeof e.data == "string") {
      var payload = JSON.parse(e.data);
      //console.log("payload= " + JSON.stringify(payload, null, 2));
      if ("method" in payload) {
        var method = '_' + payload['method'];
        console.log('dispatch message ' + payload['_id'] + ' to function ' + method);
        result = executeFunctionByName(method, window, payload);
        if (result != null) {
          result['_response_to'] = payload['_id'];
          result['_query'] = payload;
          //console.log("function " + method + " returned " + JSON.stringify(result, null, 2));
          send(result);
        }
      } else if ("_response_to" in payload) {
        if ('id' in payload) {
          console.log('got response for id='+payload['id']);
        }
        console.log('got a response to message ' + payload['_response_to']);
      } else {
        console.log("don't know what to do with message " + e.data);
      }
    } else {
      var arr = new Uint8Array(e.data);
      var hex = '';
      for (var i = 0; i < arr.length; i++) {
        hex += ('00' + arr[i].toString(16)).substr(-2);
      }
      console.log("Binary message received: " + hex);
    }
  };

  socket.onclose = function (e) {
    clearInterval(check_interval); 
    console.log("Connection closed. Reason: " + e.reason);
  };

}
