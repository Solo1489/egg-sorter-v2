// ข้อความมุมจอ: ผลตรวจสเปก, เวลาที่เล่น, event/note ของแอนิเมชัน และคำเตือน

function createElement(tag, className, text = '') {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

export function createHud(element) {
  const title = createElement('p', 'hud-title');
  const statusList = createElement('div', 'hud-status-list');
  const playback = createElement('p', 'hud-playback');
  const messageList = createElement('ul', 'hud-messages');
  const warning = createElement('p', 'hud-warning');
  element.append(title, statusList, playback, messageList, warning);

  const statusRows = new Map();
  let messagesKey = '';

  return {
    setTitle(text) {
      title.textContent = text;
    },

    /** แสดง/อัปเดตสถานะหนึ่งบรรทัด (จุดเขียว = ผ่าน, จุดแดง = ไม่ผ่าน) */
    setStatus(key, { ok, text, detail = '' }) {
      let row = statusRows.get(key);
      if (!row) {
        row = createElement('p', 'hud-status');
        row.append(document.createElement('span'));
        statusList.append(row);
        statusRows.set(key, row);
      }
      row.dataset.ok = String(ok);
      const content = row.firstElementChild;
      content.textContent = text;
      if (detail) content.append(createElement('small', '', detail));
    },

    setPlayback(text) {
      if (playback.textContent !== text) playback.textContent = text;
    },

    /** @param {Array<{t, kind, text, seqId}>} messages ใหม่สุดก่อน */
    setMessages(messages) {
      const key = messages.map((message) => `${message.t}|${message.text}`).join('\n');
      if (key === messagesKey) return;
      messagesKey = key;
      messageList.replaceChildren(
        ...messages.map((message) => {
          const item = createElement('li', `hud-message hud-message--${message.kind}`);
          item.append(createElement('span', 'hud-message-tag', message.seqId), message.text);
          return item;
        }),
      );
    },

    setWarning(text) {
      warning.textContent = text ?? '';
    },
  };
}
