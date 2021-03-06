
const BASE_URL = "";

// Caching some frequently accessed DOM elements:
const $body = $("body");
const $dmDiv = $("#direct-message-div");
const $dmList = $(".direct-messages-list");


// Handle like/dislike via ajax:
$body.on("click", ".fa-heart", async function (evt) {
  evt.preventDefault();

  // Grabbing the action from the grandparent:
  let action = $(this).parent().parent().attr("action");

  // Make the post request:
  const response = await $.post(BASE_URL + action);

  // Toggle the class to like/unlike:
  if (response.status === 'liked') {
    $(this).removeClass('far').addClass('fas');
  }
  else {
    $(this).removeClass('fas').addClass('far');
  }
  evt.preventDefault();

});

// POST: Event listner to submit a post request for adding a warble 
$("#add-warble-form").on("submit", async function (evt) {
  evt.preventDefault();

  // Create ajax post:
  const response = await $.ajax({
    type: "POST",
    url: BASE_URL + '/messages/new',
    // need to serialize 'this' for post body:
    data: $(this).serialize(),
    // do a windows reload to close modal and
    // display new warbles
    success: function (data) {
      window.location.reload();
    },
    // To make wtforms CSRF check happy:
    headers: {
      "X-CSRFToken": "{{ form.csrf_token._value() }}"
    }
  });

});

// GET: Get the form for the warble div
$("#new-yak-btn").on("click", async function (evt) {
  evt.preventDefault();

  const response = await $.get(BASE_URL + '/messages/new');

  $("#add-yak-div").append(response.form.csrf_token);
  let $text_element = $(response.form.text)
    .attr("placeholder", "What's happening?")
    .attr("class", "form-control")
    .attr("rows", 3)
    .attr("id", "yak-text");

  $("#add-yak-div").append($text_element);

});

/*********************************** DIRECTMESSAGE  **************/
// direct message form : 
$("#direct-message-btn").on("click", async function (evt) {
  evt.preventDefault();

  const response = await $.get(BASE_URL + '/directmessage/new');

  // Clear out the DM form div:
  $dmDiv.empty();

  // Add the CSRF token:
  $dmDiv.append(response.form.csrf_token);


  // Create the to-user input text element w/attributes:
  let $to_element = $(response.form.to_user)
    .attr("data-toggle", "dropdown")
    .attr("placeholder", "To...")
    .attr("class", "form-control")
    .attr("type", "search");
  $dmDiv.append($to_element);


  // Autocomplete
  let $auto = $(`<div id="autocomplete-to_user" class="dropdown-menu" aria-labelledby="dropdownMenuButton"></div>`);
  $dmDiv.append($auto);


  // Then text area w/attributes:
  let $text_element = $(response.form.text)
    .attr("placeholder", "What would you like to say?")
    .attr("class", "form-control")
    .attr("rows", 5)
    .attr("cols", 30)
    .attr("maxlength", 140)
    .attr("id", "dm-message");

  $dmDiv.append($text_element);


  // LOAD MESSAGES:
  loadDirectMessages();

});


$("#direct-message-form").on("submit", async function (evt) {
  evt.preventDefault();
  // Create ajax post:
  const response = await $.ajax({
    type: "POST",
    url: BASE_URL + '/directmessage/new',

    // need to serialize 'this' for post body:
    data: $(this).serialize(),

    // To make wtforms CSRF check happy:
    headers: {
      "X-CSRFToken": "{{ form.csrf_token._value() }}"
    }
  });

  if (response.status === "success") {
    window.location.reload();
  } else if (response.form.user_error) {
    let err_html = `<span class="text-danger">${response.form.user_error}</span>`;
    $dmDiv.append(err_html);
  }

});


async function loadDirectMessages() {

  // When loading the direct messages modal
  // we'll want to query for unread messages 
  // and up to 5 or 10 most recent messages....
  // These will be both sent by the user and
  // received from other uses.
  // 1 - on loading the modal query for messages
  // 2 - loop through returned messages and format
  //     output
  // 3 - append to $dmList


  const response = await $.get(BASE_URL + '/directmessage/list');

  let messageList = '';

  if (response.length > 0) {


    // Show the most recent 5 direct messages:
    for (let i = 0; i < Math.min(response.length, 5); i++) {

      const dm = response[i];
      // dm.
      // from_userid: 301
      // from_userimage: "https://images.homedepot-static.com/productImages/11b187f7-cdfc-49c7-bb44-31ec62d84f38/svn/black-fanmats-sports-rugs-18885-64_1000.jpg"
      // from_username: "sharks"
      // read: false
      // text: "lets see if this one works at 11:50."
      // timestamp: "Fri, 26 Apr 2019 11:51:00 GMT"
      // to_userid: 301
      // to_userimage: "https://images.homedepot-static.com/productImages/11b187f7-cdfc-49c7-bb44-31ec62d84f38/svn/black-fanmats-sports-rugs-18885-64_1000.jpg"
      // to_username: "sharks"

      let timestamp = new Date(dm.timestamp);


      messageList += `<div class="d-flex justify-content-between pt-3 px-3 border-top">
                                <span><img class="timeline-image" src="${dm.from_userimage}" alt="logo"><span class="h5 pl-2">@${dm.from_username}</span></span>
                                <span class="pt-2 h6">${timestamp.toLocaleString()}</span>
                            </div>
                            <p class="px-3 pt-2">${dm.text}</p>`;

    }

    $dmList.append(messageList);
  }

}


/*********************************** AUTOCOMPLETE  */
// Auto complete : Typing regular characters
$body.on("keypress", "#to_user, #search", debounce(async function (evt) {

  let $input = $(this);
  // Grab the text typed
  let text = $input.val();

  // Grab the array of autocompleted suggestions
  let response = await $.get(`${BASE_URL}/autocomplete`, { subword: text });

  updateAutoCompleteUI(response.autocomplete, $input.attr("id"));

}, 500));

// Just for backspace
$body.on("keydown", "#to_user, #search", debounce(async function (evt) {
  let $input = $(this);

  if (evt.keyCode === 8) {
    let text = $input.val();

    // Only show suggestions if the text field is not empty
    if (text.length > 0) {
      // Grab the array of autocompleted suggestions
      let response = await $.get(`${BASE_URL}/autocomplete`, { subword: text });
      updateAutoCompleteUI(response.autocomplete, $input.attr("id"));
    } else {
      $input.empty();
    }
  }
}, 500));

// Updates the autocomplete UI with an array of usernames
function updateAutoCompleteUI(usernamesArray, input_id) {

  let $autocomplete = $(`#autocomplete-${input_id}`);
  $autocomplete.empty();
  for (let username of usernamesArray) {
    let autoForm = $(`<a class="dropdown-item">${username}</a>`);
    $autocomplete.append(autoForm);
  }
}

// Selection from the autocomplete
$body.on("click", ".dropdown-item", function (evt) {

  evt.preventDefault();
  let text = $(this).text();
  // Grab the inputtextID based off the current clicked div
  let inputTextId = $(this).parent().attr('id').split('-')[1];

  // Set the text
  $(`#${inputTextId}`).val(text);
});


/** debouncing function:
 * https://ourcodeworld.com/articles/read/16/what-is-the-debounce-method-and-how-to-use-it-in-javascript
 */
function debounce(func, wait, immediate) {
  let timeout;
  return function () {
    let context = this;
    let args = arguments;
    let later = function () {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };
    var callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func.apply(context, args);
  };

}
