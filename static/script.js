// @ts-nocheck
/*
 * Hayatee — chat UI logic
 * ---------------------------------------------------------------
 * Sections below:
 *   1. Loading screen dismissal
 *   2. Element references
 *   3. Canned bot response data (replace with a real API call)
 *   4. Helper functions (time formatting, scrolling, DOM building)
 *   5. Core chat actions (send message, get bot reply, new chat)
 *   6. Event bindings
 * ---------------------------------------------------------------
 */
(function () {
  let sessionId;
  const origin = window.location.origin;
  /* ---------------------------------------------------------
     1. Loading screen
     Shown immediately on load; fades out shortly after the
     window's "load" event so the throb animation is visible
     even on fast connections.
     --------------------------------------------------------- */
  const loadingScreen = document.getElementById('loadingScreen');
  window.addEventListener('load', function () {
    setTimeout(function () {
      loadingScreen.classList.add('hidden');
    }, 1800);
  });

  /* ---------------------------------------------------------
     2. Element references
     --------------------------------------------------------- */
  const chat = document.getElementById('chat');               // scrollable message list
  const welcomeState = document.getElementById('welcomeState'); // empty-state / starter chips
  const form = document.getElementById('inputForm');          // composer <form>
  const input = document.getElementById('messageInput');      // auto-growing textarea
  const sendBtn = document.getElementById('sendBtn');         // disabled until there's text
  const newChatBtn = document.getElementById('newChatBtn');   // header "+" button
  const starters = document.querySelectorAll('.starter-chip'); // welcome-state topic chips

  /* ---------------------------------------------------------
     3. Canned bot responses (stub)
     Keyed by the lowercased user message. Swap botRespond()
     below for a real fetch() call to your backend/LLM when
     you're ready to go live — the addMessage() signature
     (sender, text, quickReplies) stays the same either way.
     --------------------------------------------------------- */
  const BOT_REPLIES = {
    "i'd like to check my symptoms": {
      text: "Sure — I can help narrow that down. What's the main symptom you're noticing right now?",
      quick: ["Fever", "Headache", "Cough", "Stomach pain"]
    },
    "i want to book an appointment": {
      text: "Happy to help. What type of visit are you looking for?",
      quick: ["General check-up", "Follow-up", "Specialist referral"]
    },
    "i have a question about my medication": {
      text: "Got it. Could you tell me the name of the medication, or what you'd like to know about it?",
      quick: []
    },
    "talk to a human": {
      text: "Connecting you with a nurse now — average wait time is about 4 minutes. You can keep chatting with me in the meantime.",
      quick: []
    }
  };

  /* ---------------------------------------------------------
     4. Helper functions
     --------------------------------------------------------- */

  // Returns the current time as "h:mm AM/PM" for message timestamps
  function timeNow() {
    const d = new Date();
    let h = d.getHours(), m = d.getMinutes();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;           // convert 24h -> 12h, treating 0 as 12
    m = m < 10 ? '0' + m : m;     // zero-pad minutes
    return h + ':' + m + ' ' + ampm;
  }

  // Keeps the newest message in view
  function scrollToBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  // Hides the welcome/starter-chip state the first time a message is sent
  function hideWelcome() {
    if (welcomeState && welcomeState.parentNode) {
      welcomeState.style.display = 'none';
    }
  }

  // Builds and appends one chat bubble (user or bot), with optional quick-reply chips
  function addMessage(sender, text, quickReplies) {
    hideWelcome();

    const row = document.createElement('div');
    row.className = 'msg-row ' + sender; // 'bot' or 'user' controls bubble alignment/color

    // Bot messages get a robot avatar; user messages get a person
    // avatar — both sides show a circular icon, matching the reference layout
    let avatarHtml = '';
    if (sender === 'bot') {
      avatarHtml = '<div class="msg-avatar"><i class="fa-solid fa-robot" aria-hidden="true"></i></div>';
    } else {
      avatarHtml = '<div class="msg-avatar user-avatar"><i class="fa-solid fa-user" aria-hidden="true"></i></div>';
    }

    const col = document.createElement('div');
    col.className = 'bubble-col';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text; // textContent (not innerHTML) avoids markup/XSS issues with dynamic text
    col.appendChild(bubble);

    // Optional quick-reply chips: each one just re-sends its own label as a user message
    if (quickReplies && quickReplies.length) {
      const qr = document.createElement('div');
      qr.className = 'quick-replies';
      quickReplies.forEach(function (label) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'quick-reply';
        btn.textContent = label;
        btn.addEventListener('click', function () { sendMessage(label); });
        qr.appendChild(btn);
      });
      col.appendChild(qr);
    }

    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = timeNow();
    col.appendChild(time);

    row.innerHTML = avatarHtml;
    row.appendChild(col);

    chat.appendChild(row);
    scrollToBottom();
  }

  // Inserts the animated "typing…" bubble while a bot reply is pending
  function showTyping() {
    const row = document.createElement('div');
    row.className = 'msg-row bot typing-row';
    row.id = 'typingRow'; // unique id so hideTyping() can find and remove it
    row.innerHTML =
      '<div class="msg-avatar"><i class="fa-solid fa-robot" aria-hidden="true"></i></div>' +
      '<div class="typing-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
    chat.appendChild(row);
    scrollToBottom();
  }

  // Removes the typing indicator once the bot's reply is ready
  function hideTyping() {
    const row = document.getElementById('typingRow');
    if (row) row.remove();
  }

  /* ---------------------------------------------------------
     5. Core chat actions
     --------------------------------------------------------- */

  // Sends the message to the Hayati FastAPI backend.
  async function botRespond(userText) {
    showTyping();
    try {
      const response = await fetch(`${origin}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, session_id: sessionId })
      });
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      const res = await response.json();
      sessionId = res.session_id;
      addMessage('bot', res.reply);
      if (res.assessment && res.assessment.results && res.assessment.results.length) {
        const top = res.assessment.results.slice(0, 3).map(function (x) { return x.condition + " — " + x.score + "% pattern match"; }).join("\n");
        addMessage('bot', "Possible-condition assessment (not a diagnosis):\n" + top);
      }
    } catch (error) {
      addMessage('bot', "I’m having trouble connecting to Hayati right now. Please try again in a moment.");
      console.error(error);
    } finally {
      hideTyping();
    }
  }

  // Sends a message: either the composer's current text, or an explicit
  // string (used by starter chips / quick-reply buttons)
  function sendMessage(text) {
    const value = (typeof text === 'string' ? text : input.value).trim();
    if (!value) return; // ignore empty/whitespace-only submissions
    addMessage('user', value, null);
    input.value = '';
    autosize();
    updateSendState();
    botRespond(value);
  }

  // Grows the textarea to fit its content, up to a max height (CSS-matched)
  function autosize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 110) + 'px';
  }

  // Enables the send button only when there's non-whitespace text to send
  function updateSendState() {
    sendBtn.disabled = input.value.trim().length === 0;
  }

  /* ---------------------------------------------------------
     6. Event bindings
     --------------------------------------------------------- */

  // Composer submit — triggered by the send button (Enter no longer sends)
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    sendMessage();
  });

  // Keep the textarea sized and the send button state in sync as the user types
  input.addEventListener('input', function () {
    autosize();
    updateSendState();
  });

  // Enter now behaves like a normal newline in the textarea (default
  // browser behavior) — messages are only sent via the send button
  // or the form's submit event.

  // Welcome-state topic chips each send their preset message
  starters.forEach(function (chip) {
    chip.addEventListener('click', function () {
      sendMessage(chip.getAttribute('data-msg'));
    });
  });

  // Header "+" button: clears the transcript and restores the welcome state
  newChatBtn.addEventListener('click', function () {
    document.querySelectorAll('.msg-row').forEach(function (el) { el.remove(); });
    sessionId = undefined;
    if (welcomeState) welcomeState.style.display = '';
    input.value = '';
    autosize();
    updateSendState();
  });

  // Attach/mic buttons are placeholders — swap these handlers for real
  // file-input / Web Speech API integrations when ready
  document.getElementById('attachBtn').addEventListener('click', function () {
    addMessage('bot', 'Photo attachments aren\'t wired up in this template yet — hook this button up to a file input when you\'re ready.', null);
  });
  document.getElementById('micBtn').addEventListener('click', function () {
    addMessage('bot', 'Voice input isn\'t wired up in this template yet — hook this button up to the Web Speech API when you\'re ready.', null);
  });

  // Ensure the send button starts in the correct (disabled) state
  updateSendState();
})();
