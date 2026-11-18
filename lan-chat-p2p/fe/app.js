/* Zalo PC UI Controller + Optional Live P2P UDP/TCP Bridge */

const SVG_AVATARS = {
  docs: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><circle cx='40' cy='40' r='40' fill='%232b7de9'/><path d='M20 26a4 4 0 0 1 4-4h12l5 5h15a4 4 0 0 1 4 4v23a4 4 0 0 1-4 4H24a4 4 0 0 1-4-4V26z' fill='%23ffffff' opacity='0.95'/></svg>",
  nglinh: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%237c6f64'/><circle cx='40' cy='31' r='14' fill='%23f5d0b5'/><path d='M25 26c3-12 27-12 30 0' fill='%2327272a'/><path d='M18 76c4-18 40-18 44 0' fill='%23f8fafc'/></svg>",
  family: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%23b91c1c'/><circle cx='24' cy='22' r='10' fill='%23fca5a5' opacity='0.5'/><circle cx='28' cy='36' r='9' fill='%23fde68a'/><circle cx='50' cy='34' r='10' fill='%23fed7aa'/><circle cx='39' cy='46' r='8' fill='%23fde68a'/><path d='M14 74c4-15 24-15 28 0' fill='%231e293b'/><path d='M36 74c4-16 26-16 30 0' fill='%23dc2626'/></svg>",
  dad: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%23d97706'/><rect x='14' y='16' width='52' height='48' rx='6' fill='%23fef08a' stroke='%2392400e' stroke-width='3'/><text x='40' y='47' font-size='18' text-anchor='middle' fill='%2378350f' font-family='sans-serif' font-weight='bold'>DAD</text></svg>",
  calc: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%23e2e8f0'/><circle cx='26' cy='28' r='14' fill='%233b82f6'/><circle cx='54' cy='28' r='14' fill='%230ea5e9'/><circle cx='26' cy='56' r='14' fill='%2364748b'/><rect x='40' y='42' width='28' height='26' rx='12' fill='%23cbd5e1'/><text x='54' y='59' font-size='13' text-anchor='middle' fill='%231e293b' font-family='sans-serif' font-weight='bold'>82</text></svg>",
  hcmus: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%23e2e8f0'/><circle cx='26' cy='28' r='14' fill='%231e293b'/><circle cx='54' cy='28' r='14' fill='%23f8fafc' stroke='%2394a3b8'/><circle cx='26' cy='56' r='14' fill='%2394a3b8'/><rect x='40' y='42' width='28' height='26' rx='12' fill='%23cbd5e1'/><text x='54' y='59' font-size='13' text-anchor='middle' fill='%231e293b' font-family='sans-serif' font-weight='bold'>40</text></svg>",
  toby: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><circle cx='40' cy='40' r='38' fill='%23be185d'/><text x='40' y='37' font-size='13' text-anchor='middle' fill='%23ffffff' font-family='sans-serif' font-weight='bold'>TOBY</text><text x='40' y='52' font-size='9' text-anchor='middle' fill='%23fbcfe8' font-family='sans-serif'>TIẾNG ANH</text></svg>",
  zawar: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='%23fef08a'/><circle cx='40' cy='42' r='22' fill='%234d7c0f'/><rect x='24' y='34' width='32' height='10' rx='4' fill='%231e293b'/><circle cx='33' cy='39' r='3' fill='%23ef4444'/><circle cx='47' cy='39' r='3' fill='%23ef4444'/></svg>",
  stickerLaugh: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 140 140'><path d='M32 62c-8-25 18-48 48-44 26 3 44 22 36 48-5 15-16 24-42 24S37 77 32 62z' fill='%237c2d12'/><circle cx='72' cy='68' r='32' fill='%23fed7aa'/><path d='M54 58c4-5 10-5 14 0' stroke='%23431407' stroke-width='3.5' fill='none' stroke-linecap='round'/><path d='M78 58c4-5 10-5 14 0' stroke='%23431407' stroke-width='3.5' fill='none' stroke-linecap='round'/><path d='M56 74h30c0 12-30 12-30 0z' fill='%23ffffff' stroke='%23431407' stroke-width='2.5'/><path d='M48 98c6-12 42-12 48 0l4 28H44l4-28z' fill='%2384cc16' stroke='%23365314' stroke-width='2.5'/></svg>"
};

function makePeerAvatar(name) {
  const colors = ["#0068ff", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const bg = colors[Math.abs(hash) % colors.length];
  const initials = name.trim().slice(0, 2).toUpperCase();
  return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='${encodeURIComponent(bg)}'/><text x='40' y='48' font-size='28' text-anchor='middle' fill='%23ffffff' font-family='Segoe UI, sans-serif' font-weight='bold'>${initials}</text></svg>`;
}

const conversations = [
  {
    id: "my-documents",
    name: "My Documents",
    shortRightName: "My Documents",
    avatar: SVG_AVATARS.docs,
    time: "10/11",
    preview: "Bạn: 📎 25127224_Chau Hoa Phat...",
    pinned: true,
    muted: false,
    unread: 0,
    members: "Cloud của tôi",
    joinLink: "zalo.me/cloud/mydocs",
    isGroup: false,
    messages: [
      { type: "pill", text: "10/11" },
      {
        type: "outgoing",
        file: { name: "25127224_Chau Hoa Phat.pdf", size: "1.4 MB" },
        time: "09:30",
        likes: 0
      }
    ]
  },
  {
    id: "nglinh",
    name: "nglinh",
    shortRightName: "nglinh",
    avatar: SVG_AVATARS.nglinh,
    time: "2 ngày",
    preview: "🏷️ Bạn: https://maps.app.goo.gl/...",
    pinned: true,
    muted: false,
    unread: 0,
    members: "Bạn bè",
    joinLink: "zalo.me/nglinh",
    isGroup: false,
    messages: [
      { type: "pill", text: "2 ngày trước" },
      {
        type: "outgoing",
        text: "https://maps.app.goo.gl/7xZ8kLm2P",
        time: "20:15",
        likes: 1
      }
    ]
  },
  {
    id: "phats-family",
    name: "PHAT'S FAMILY (NHÀ BA K...",
    fullTitle: "PHAT'S FAMILY (NHÀ BA KU) ❤️🏠",
    shortRightName: "PHAT'S FAMILY (NHÀ BA KU...",
    avatar: SVG_AVATARS.family,
    time: "2 giờ",
    preview: "Bạn: dạ tại tối con đi chơi với bạn hihi",
    pinned: false,
    muted: true,
    unread: 0,
    members: "4 thành viên",
    joinLink: "zalo.me/g/mrvobd614",
    isGroup: true,
    messages: [
      {
        type: "sticker",
        src: SVG_AVATARS.stickerLaugh,
        time: "14:44"
      },
      { type: "pill", text: "16:56 Hôm nay" },
      {
        type: "incoming",
        sender: "Dad",
        senderAvatar: SVG_AVATARS.dad,
        text: "Sao đặt vé khuya quá vậy con",
        time: "16:56"
      },
      { type: "pill", text: "18:10 Hôm nay" },
      {
        type: "outgoing",
        text: "dạ tại tối con đi chơi với bạn hihi",
        time: "18:10",
        hearts: 2,
        showSeenAvatars: true
      }
    ]
  },
  {
    id: "vi-tich-phan-2",
    name: "TH - Vi tích phân 2 - 25C01",
    shortRightName: "TH - Vi tích phân 2 - 25C01",
    avatar: SVG_AVATARS.calc,
    time: "5 giờ",
    preview: "Lê Hải Thiên: 📎 Chương 3 - THVTP2B...",
    pinned: false,
    muted: false,
    unread: 0,
    members: "82 thành viên",
    joinLink: "zalo.me/g/vtp2_25c01",
    isGroup: true,
    messages: [
      { type: "pill", text: "Hôm nay" },
      {
        type: "incoming",
        sender: "Lê Hải Thiên",
        senderAvatar: makePeerAvatar("LT"),
        file: { name: "Chương 3 - THVTP2B.pdf", size: "2.8 MB" },
        time: "15:10"
      }
    ]
  },
  {
    id: "25c02-hcmus",
    name: "25C02 - K25TCTA - HCMUS",
    shortRightName: "25C02 - K25TCTA - HCMUS",
    avatar: SVG_AVATARS.hcmus,
    time: "5 giờ",
    preview: "Thanh Hương: các bạn thông tin ...",
    pinned: false,
    muted: false,
    unread: 0,
    members: "40 thành viên",
    joinLink: "zalo.me/g/25c02hcmus",
    isGroup: true,
    messages: [
      { type: "pill", text: "Hôm nay" },
      {
        type: "incoming",
        sender: "Thanh Hương",
        senderAvatar: makePeerAvatar("TH"),
        text: "các bạn thông tin lịch học tuần tới nhé",
        time: "15:02"
      }
    ]
  },
  {
    id: "toby-english",
    name: "GB Toby Tiếng Anh Rạch Giá",
    shortRightName: "GB Toby Tiếng Anh Rạch Giá",
    avatar: SVG_AVATARS.toby,
    time: "9 giờ",
    preview: "📊 Joseph tham gia cuộc bình chọn: ...",
    pinned: false,
    muted: true,
    unread: 0,
    members: "28 thành viên",
    joinLink: "zalo.me/g/tobyrg",
    isGroup: true,
    messages: [
      { type: "pill", text: "Hôm nay" },
      {
        type: "incoming",
        sender: "Joseph",
        senderAvatar: makePeerAvatar("JS"),
        text: "📊 Joseph tham gia cuộc bình chọn: Lịch học tối thứ 6",
        time: "11:20"
      }
    ]
  },
  {
    id: "za-war",
    name: "ZA War - Survival VN",
    shortRightName: "ZA War - Survival VN",
    avatar: SVG_AVATARS.zawar,
    time: "9 giờ",
    preview: "[Truyền Thông Game Mới] 🎮 VÕ ...",
    pinned: false,
    muted: true,
    unread: 0,
    members: "512 thành viên",
    joinLink: "zalo.me/g/zawarsvn",
    isGroup: true,
    messages: [
      { type: "pill", text: "Hôm nay" },
      {
        type: "incoming",
        sender: "Admin",
        senderAvatar: SVG_AVATARS.zawar,
        text: "[Truyền Thông Game Mới] 🎮 VÕ LÂM SINH TỒN chính thức mở server!",
        time: "11:05"
      }
    ]
  }
];

let activeId = "phats-family";
let currentFilter = "all";
let searchQuery = "";
let myStatus = "online";
let backendAvailable = false;

const convListEl = document.getElementById("convList");
const chatMessagesEl = document.getElementById("chatMessages");
const activeHeaderAvatarEl = document.getElementById("activeHeaderAvatar");
const activeChatTitleEl = document.getElementById("activeChatTitle");
const activeMemberCountEl = document.getElementById("activeMemberCount");
const messageInputEl = document.getElementById("messageInput");
const messageFormEl = document.getElementById("messageForm");
const sendOrLikeBtnEl = document.getElementById("sendOrLikeBtn");
const infoSidebarEl = document.getElementById("infoSidebar");
const infoAvatarLargeEl = document.getElementById("infoAvatarLarge");
const infoGroupNameEl = document.getElementById("infoGroupName");
const infoMemberRowEl = document.getElementById("infoMemberRow");
const infoJoinLinkEl = document.getElementById("infoJoinLink");
const infoHeaderTitleEl = document.getElementById("infoHeaderTitle");
const transferBarEl = document.getElementById("transferBar");
const transferLabelEl = document.getElementById("transferLabel");
const transferFillEl = document.getElementById("transferFill");
const transferPctEl = document.getElementById("transferPct");

function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function getActiveConversation() {
  return conversations.find((c) => c.id === activeId) || conversations[2];
}

function renderConversationList() {
  convListEl.innerHTML = "";
  const q = searchQuery.trim().toLowerCase();

  const filtered = conversations.filter((c) => {
    if (currentFilter === "unread" && (!c.unread || c.unread <= 0)) {
      return false;
    }
    if (q && !c.name.toLowerCase().includes(q) && !(c.fullTitle || "").toLowerCase().includes(q)) {
      return false;
    }
    return true;
  });

  filtered.forEach((conv) => {
    const item = document.createElement("div");
    item.className = `conv-item${conv.id === activeId ? " active" : ""}${conv.unread > 0 ? " unread" : ""}`;
    item.onclick = () => selectConversation(conv.id);

    const dotHtml = conv.peerStatus
      ? `<span class="conv-peer-dot ${conv.peerStatus}"></span>`
      : "";

    const muteIcon = conv.muted ? `<span title="Đã tắt thông báo">🔕</span>` : "";
    const rightBadgeOrPin =
      conv.unread > 0
        ? `<span class="conv-unread-badge">${conv.unread}</span>`
        : conv.pinned
          ? `<span class="conv-pin" title="Đã ghim">📌</span>`
          : "";

    item.innerHTML = `
      <div class="conv-avatar">
        <img src="${conv.avatar}" alt="${conv.name}" />
        ${dotHtml}
      </div>
      <div class="conv-body">
        <div class="conv-top-row">
          <div class="conv-name">${conv.name}</div>
          <div class="conv-time">${muteIcon}<span>${conv.time}</span></div>
        </div>
        <div class="conv-bottom-row">
          <div class="conv-preview">${conv.preview}</div>
          ${rightBadgeOrPin}
        </div>
      </div>
    `;
    convListEl.appendChild(item);
  });
}

function renderActiveChat() {
  const conv = getActiveConversation();
  const displayTitle = conv.fullTitle || conv.name;

  activeHeaderAvatarEl.innerHTML = `<img src="${conv.avatar}" alt="${conv.name}" />`;
  activeChatTitleEl.textContent = displayTitle;
  activeMemberCountEl.textContent = conv.members;
  messageInputEl.placeholder = `Nhập @, tin nhắn tới ${displayTitle}`;

  infoHeaderTitleEl.textContent = conv.isGroup ? "Thông tin nhóm" : "Thông tin hội thoại";
  infoAvatarLargeEl.innerHTML = `<img src="${conv.avatar}" alt="${conv.name}" />`;
  infoGroupNameEl.textContent = conv.shortRightName || conv.name;
  infoMemberRowEl.textContent = conv.members;
  infoJoinLinkEl.textContent = conv.joinLink || "lan://p2p-socket";

  chatMessagesEl.innerHTML = "";

  conv.messages.forEach((m, idx) => {
    if (m.type === "pill") {
      const pillRow = document.createElement("div");
      pillRow.className = "time-pill-row";
      pillRow.innerHTML = `<span class="time-pill">${m.text}</span>`;
      chatMessagesEl.appendChild(pillRow);
      return;
    }

    if (m.type === "sticker") {
      const sRow = document.createElement("div");
      sRow.className = "sticker-row";
      sRow.innerHTML = `
        <div class="sticker-wrap">
          <button class="sticker-dl-btn" title="Tải sticker">&#10515;</button>
          <img class="sticker-img" src="${m.src}" alt="sticker" />
        </div>
        <span class="sticker-time">${m.time}</span>
      `;
      chatMessagesEl.appendChild(sRow);
      return;
    }

    const row = document.createElement("div");
    row.className = `msg-row ${m.type}`;

    const avatarHtml =
      m.type === "incoming"
        ? `<div class="msg-sender-avatar"><img src="${m.senderAvatar || conv.avatar}" alt="${m.sender || conv.name}" /></div>`
        : "";

    const senderHtml =
      m.type === "incoming" && m.sender
        ? `<div class="msg-sender-name">${m.sender}</div>`
        : "";

    let bodyHtml = "";
    if (m.file) {
      const dlAttr = m.file.url ? `href="${m.file.url}" download="${m.file.name}"` : `href="#file" onclick="return false;"`;
      bodyHtml = `
        <a ${dlAttr} style="text-decoration:none;">
          <div class="msg-file-card">
            <div class="msg-file-icon">📄</div>
            <div class="msg-file-meta">
              <span class="msg-file-name">${m.file.name}</span>
              <span class="msg-file-size">${m.file.size || "Đã nhận qua TCP"}</span>
            </div>
          </div>
        </a>
      `;
    } else {
      bodyHtml = `<div class="msg-text">${escapeHtml(m.text || "")}</div>`;
    }

    let reactionHtml = "";
    if (m.hearts && m.hearts > 0) {
      reactionHtml = `
        <div class="reaction-cluster">
          <span class="reaction-pill" data-idx="${idx}">❤️ ${m.hearts}</span>
          <button class="reaction-like-btn" data-idx="${idx}" title="Thả cảm xúc">👍</button>
        </div>
      `;
    } else {
      reactionHtml = `<button class="reaction-hover-btn" data-idx="${idx}" title="Thích">👍</button>`;
    }

    row.innerHTML = `
      ${avatarHtml}
      <div class="msg-bubble">
        ${senderHtml}
        ${bodyHtml}
        <div class="msg-time">${m.time || ""}</div>
        ${reactionHtml}
      </div>
    `;

    row.querySelectorAll("[data-idx]").forEach((btn) => {
      btn.onclick = () => {
        m.hearts = (m.hearts || 0) + 1;
        renderActiveChat();
      };
    });

    chatMessagesEl.appendChild(row);

    if (m.showSeenAvatars) {
      const seenRow = document.createElement("div");
      seenRow.className = "seen-avatars-row";
      seenRow.innerHTML = `
        <img class="seen-mini" src="${SVG_AVATARS.dad}" alt="seen" />
        <img class="seen-mini" src="${SVG_AVATARS.family}" alt="seen" />
      `;
      chatMessagesEl.appendChild(seenRow);
    }
  });

  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function selectConversation(id) {
  activeId = id;
  const conv = getActiveConversation();
  conv.unread = 0;

  if (backendAvailable && conv.isLanPeer) {
    try {
      await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: conv.peerName })
      });
    } catch (_) {}
  }

  renderConversationList();
  renderActiveChat();
  messageInputEl.focus();
}

/* Composer Input & Send Logic */
messageInputEl.addEventListener("input", () => {
  const hasText = messageInputEl.value.trim().length > 0;
  if (hasText) {
    sendOrLikeBtnEl.textContent = "GỬI";
    sendOrLikeBtnEl.classList.add("send-mode");
  } else {
    sendOrLikeBtnEl.textContent = "👍";
    sendOrLikeBtnEl.classList.remove("send-mode");
  }
});

messageFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = messageInputEl.value.trim();
  const textToSend = raw || "👍";
  messageInputEl.value = "";
  sendOrLikeBtnEl.textContent = "👍";
  sendOrLikeBtnEl.classList.remove("send-mode");

  const conv = getActiveConversation();
  const timeStr = nowHHMM();

  if (backendAvailable && conv.isLanPeer) {
    try {
      await fetch("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: conv.peerName, text: textToSend })
      });
      await pollBackendState();
      return;
    } catch (_) {}
  }

  conv.messages.push({
    type: "outgoing",
    text: textToSend,
    time: timeStr,
    hearts: 0
  });
  conv.preview = `Bạn: ${textToSend}`;
  conv.time = "Vừa xong";
  renderConversationList();
  renderActiveChat();
});

/* File Transfer via Paperclip Button */
const attachFileBtn = document.getElementById("attachFileBtn");
const hiddenFileInput = document.getElementById("hiddenFileInput");

attachFileBtn.addEventListener("click", () => {
  hiddenFileInput.click();
});

hiddenFileInput.addEventListener("change", async () => {
  const file = hiddenFileInput.files[0];
  if (!file) return;
  hiddenFileInput.value = "";

  const conv = getActiveConversation();
  const sizeFormatted =
    file.size < 1024 * 1024
      ? `${(file.size / 1024).toFixed(1)} KB`
      : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

  if (backendAvailable && conv.isLanPeer) {
    const formData = new FormData();
    formData.append("target", conv.peerName);
    formData.append("file", file);
    transferBarEl.classList.remove("hidden");
    transferLabelEl.textContent = `Đang gửi ${file.name}...`;
    transferFillEl.style.width = "40%";
    transferPctEl.textContent = "40%";
    try {
      await fetch("/api/send_file", {
        method: "POST",
        body: formData
      });
      transferFillEl.style.width = "100%";
      transferPctEl.textContent = "100%";
      setTimeout(() => transferBarEl.classList.add("hidden"), 900);
      await pollBackendState();
      return;
    } catch (_) {
      transferBarEl.classList.add("hidden");
    }
  }

  // Local UI simulation with progress bar
  transferBarEl.classList.remove("hidden");
  transferLabelEl.textContent = `Sending ${file.name} (${sizeFormatted})...`;
  transferFillEl.style.width = "60%";
  transferPctEl.textContent = "60%";

  setTimeout(() => {
    transferFillEl.style.width = "100%";
    transferPctEl.textContent = "100%";
    conv.messages.push({
      type: "outgoing",
      file: { name: file.name, size: sizeFormatted },
      time: nowHHMM()
    });
    conv.preview = `Bạn: 📎 ${file.name}`;
    conv.time = "Vừa xong";
    renderConversationList();
    renderActiveChat();
    setTimeout(() => transferBarEl.classList.add("hidden"), 600);
  }, 350);
});

/* Sticker quick send */
document.getElementById("stickerBtn").addEventListener("click", () => {
  const conv = getActiveConversation();
  conv.messages.push({
    type: "sticker",
    src: SVG_AVATARS.stickerLaugh,
    time: nowHHMM()
  });
  conv.preview = "Bạn: [Sticker]";
  conv.time = "Vừa xong";
  renderConversationList();
  renderActiveChat();
});

/* Tabs, Search, Banner & Right Panel Toggle */
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter || "all";
    renderConversationList();
  });
});

document.getElementById("searchInput").addEventListener("input", (e) => {
  searchQuery = e.target.value;
  renderConversationList();
});

document.getElementById("closeBannerBtn").addEventListener("click", () => {
  document.getElementById("zcloudBanner").classList.add("hidden");
});

document.getElementById("toggleRightPanelBtn").addEventListener("click", (e) => {
  infoSidebarEl.classList.toggle("hidden");
  e.currentTarget.classList.toggle("active-panel-btn");
});

/* Toggle UDP Online/Away status */
document.getElementById("toggleStatusBtn").addEventListener("click", async () => {
  myStatus = myStatus === "online" ? "away" : "online";
  const dot = document.getElementById("myStatusDot");
  dot.className = `status-dot ${myStatus}`;
  if (backendAvailable) {
    try {
      await fetch("/api/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: myStatus })
      });
    } catch (_) {}
  }
});

/* Optional Live Polling Bridge to Python UDPDiscovery + TCPManager (fe/server.py) */
async function pollBackendState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    backendAvailable = true;

    if (data.selfName) {
      document.getElementById("windowTitle").textContent = `Zalo - ${data.selfName} (TCP :${data.tcpPort} | UDP :${data.udpPort})`;
    }

    if (data.transfer && data.transfer.active) {
      transferBarEl.classList.remove("hidden");
      transferLabelEl.textContent = data.transfer.label;
      transferFillEl.style.width = `${data.transfer.pct}%`;
      transferPctEl.textContent = `${data.transfer.pct}%`;
    } else if (data.transfer && !data.transfer.active) {
      transferBarEl.classList.add("hidden");
    }

    (data.peers || []).forEach((peer) => {
      const convId = `lan-peer-${peer.name}`;
      let conv = conversations.find((c) => c.id === convId);
      const history = (data.histories && data.histories[peer.name]) || [];
      const unreadCount = (data.unreads && data.unreads[peer.name]) || 0;
      const lastItem = history.length > 0 ? history[history.length - 1] : null;
      const previewText = lastItem
        ? `${lastItem.sender === data.selfName ? "Bạn" : lastItem.sender}: ${lastItem.text}`
        : `[LAN P2P] ${peer.ip}:${peer.tcp_port} (${peer.status})`;

      const mappedMessages = [
        { type: "pill", text: `Kết nối LAN P2P (${peer.ip}:${peer.tcp_port})` },
        ...history.map((h) => ({
          type: h.sender === data.selfName ? "outgoing" : "incoming",
          sender: h.sender,
          senderAvatar: makePeerAvatar(h.sender),
          text: h.file ? undefined : h.text,
          file: h.file || undefined,
          time: h.time || "Hôm nay"
        }))
      ];

      if (!conv) {
        conv = {
          id: convId,
          isLanPeer: true,
          peerName: peer.name,
          name: `${peer.name} (LAN)`,
          fullTitle: `${peer.name} — ${peer.ip}:${peer.tcp_port}`,
          shortRightName: peer.name,
          avatar: makePeerAvatar(peer.name),
          peerStatus: peer.status,
          time: "LAN",
          preview: previewText,
          pinned: true,
          muted: false,
          unread: activeId === convId ? 0 : unreadCount,
          members: `${peer.ip}:${peer.tcp_port} (${peer.status})`,
          joinLink: `tcp://${peer.ip}:${peer.tcp_port}`,
          isGroup: false,
          messages: mappedMessages
        };
        conversations.unshift(conv);
      } else {
        conv.peerStatus = peer.status;
        conv.preview = previewText;
        conv.members = `${peer.ip}:${peer.tcp_port} (${peer.status})`;
        conv.unread = activeId === convId ? 0 : unreadCount;
        conv.messages = mappedMessages;
      }
    });

    renderConversationList();
    if (getActiveConversation().isLanPeer) {
      renderActiveChat();
    }
  } catch (_) {
    backendAvailable = false;
  }
}

/* Initial Render */
renderConversationList();
renderActiveChat();
setInterval(pollBackendState, 1000);
pollBackendState();
