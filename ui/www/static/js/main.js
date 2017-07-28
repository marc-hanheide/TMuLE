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

function _send_btn_text(text) {
  console.log('_send_btn_text: ' + text);
  msg = {
    'method': "dialog_button",
    'text': text
  };
  send(msg);
}

function _show_buttons(json) {
  console.log(json);
  //var data = JSON.parse(json);
  var btns = json["buttons"]; 
  var html = '<div class="btn-group" role="group">';
  for (d in btns) {
    console.log('add button ' + btns[d])
    html +=  '<button type="button" class="btn-lg btn-primary"' + 
                ' onclick="_send_btn_text(\''+ btns[d] +'\')">' +
                btns[d] +
                '</button>';
  }
  html += "</div>";
  console.log(html);
  $('#dialog-buttons').html(html);

}

function _show_continue_button(json) {
  console.log('show continue button');
  //var data = JSON.parse(json);
  var opt = json["options"]; 
  console.log(opt);

  if (opt.length > 0 && opt[0] == 'show') {
      $('#continue_panel').show();
  } else {
      $('#continue_panel').hide();
  }
}



function _modal_dlg(payload) {
  $('#'+payload['id']).modal();
  return {'dlg_result': true};
}



function init() {
  var host_name = window.location.hostname;
  socket = new ReconnectingWebSocket("ws://" + host_name + ":8128");
  socket.binaryType = "arraybuffer";

  socket.onopen = function () {
    console.log("Connected!");
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
    socket = null;
    console.log("Connection closed. Reason: " + e.reason);
  };

}
