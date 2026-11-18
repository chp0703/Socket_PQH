/* Zalo LAN P2P Frontend Controller */

function makePeerAvatar(name) {
  const colors = ["#0068ff", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"];
  let hash = 0;
  const clean = (name || "U").trim();
  for (let i = 0; i < clean.length; i++) {
    hash = clean.charCodeAt(i) + ((hash << 5) - hash);
  }
  const bg = colors[Math.abs(hash) % colors.length];
  const initials = clean.slice(0, 2).toUpperCase();
  return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' fill='${encodeURIComponent(bg)}'/><text x='40' y='49' font-size='27' text-anchor='middle' fill='%23ffffff' font-family='Segoe UI, sans-serif' font-weight='bold'>${initials}</text></svg>`;
}

const STICKER_LAUGH =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 140 140'><path d='M32 62c-8-25 18-48 48-44 26 3 44 22 36 48-5 15-16 24-42 24S37 77 32 62z' fill='%237c2d12'/><circle cx='72' cy='68' r='32' fill='%23fed7aa'/><path d='M54 58c4-5 10-5 14 0' stroke='%23431407' stroke-width='3.5' fill='none' stroke-linecap='round'/><path d='M78 58c4-5 10-5 14 0' stroke='%23431407' stroke-width='3.5' fill='none' stroke-linecap='round'/><path d='M56 74h30c0 12-30 12-30 0z' fill='%23ffffff' stroke='%23431407' stroke-width='2.5'/><path d='M48 98c6-12 42-12 48 0l4 28H44l4-28z' fill='%2384cc16' stroke='%23365314' stroke-width='2.5'/></svg>";

/* State: ONLY real LAN peers discovered via UDP or connected via TCP */
let lanPeers = [];
let activePeerName = null;
let infoPanelOpen = true;
let currentFilter = "all";
let searchQuery = "";
let selfName = "Tôi";
let myStatus = "online";

const convListEl = document.getElementById("convList");
const emptyChatScreenEl = document.getElementById("emptyChatScreen");
const activeChatContainerEl = document.getElementById("activeChatContainer");
const chatMessagesEl = document.getElementById("chatMessages");
const activeHeaderAvatarEl = document.getElementById("activeHeaderAvatar");
const activeChatTitleEl = document.getElementById("activeChatTitle");
const activePeerStatusTextEl = document.getElementById("activePeerStatusText");
const activePeerEndpointEl = document.getElementById("activePeerEndpoint");
const messageInputEl = document.getElementById("messageInput");
const messageFormEl = document.getElementById("messageForm");
const sendOrLikeBtnEl = document.getElementById("sendOrLikeBtn");
const infoSidebarEl = document.getElementById("infoSidebar");
const infoPullTabEl = document.getElementById("infoPullTab");
const infoResizeHandleEl = document.getElementById("infoResizeHandle");
const toggleRightPanelBtnEl = document.getElementById("toggleRightPanelBtn");
const infoAvatarLargeEl = document.getElementById("infoAvatarLarge");
const infoGroupNameEl = document.getElementById("infoGroupName");
const infoPeerAddressEl = document.getElementById("infoPeerAddress");
const infoPeerStatusEl = document.getElementById("infoPeerStatus");
const sharedFilesListEl = document.getElementById("sharedFilesList");
const totalUnreadBadgeEl = document.getElementById("totalUnreadBadge");
const transferBarEl = document.getElementById("transferBar");
const transferLabelEl = document.getElementById("transferLabel");
const transferFillEl = document.getElementById("transferFill");
const transferPctEl = document.getElementById("transferPct");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function isImageFilename(name) {
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(name || "");
}

function getActivePeer() {
  if (!activePeerName) return null;
  return lanPeers.find((p) => p.name === activePeerName) || null;
}

/* Open a file immediately on OS (via /api/open_file) and fallback to browser tab */
async function openFileImmediately(filename, url) {
  try {
    const res = await fetch("/api/open_file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename })
    });
    const data = await res.json();
    if (data && data.openedOnOS) {
      return;
    }
  } catch (_) {}
  if (url) {
    window.open(url, "_blank");
  }
}

/* Reveal file inside lan-chat-p2p/downloads/ in Windows Explorer */
async function revealFileInDownloads(filename) {
  try {
    await fetch("/api/reveal_file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename })
    });
  } catch (_) {}
}

function updateRightPanelVisibility() {
  const peer = getActivePeer();
  if (!peer) {
    infoSidebarEl.classList.add("hidden");
    infoPullTabEl.classList.add("hidden");
    return;
  }
  if (infoPanelOpen) {
    infoSidebarEl.classList.remove("hidden");
    infoPullTabEl.classList.add("hidden");
    toggleRightPanelBtnEl.classList.add("active-panel-btn");
  } else {
    infoSidebarEl.classList.add("hidden");
    infoPullTabEl.classList.remove("hidden");
    toggleRightPanelBtnEl.classList.remove("active-panel-btn");
  }
}

function renderConversationList() {
  convListEl.innerHTML = "";
  const q = searchQuery.trim().toLowerCase();

  let totalUnread = 0;
  lanPeers.forEach((p) => {
    totalUnread += p.unread || 0;
  });
  if (totalUnread > 0) {
    totalUnreadBadgeEl.textContent = String(totalUnread);
    totalUnreadBadgeEl.classList.remove("hidden");
  } else {
    totalUnreadBadgeEl.classList.add("hidden");
  }

  const filtered = lanPeers.filter((p) => {
    if (currentFilter === "unread" && (!p.unread || p.unread <= 0)) {
      return false;
    }
    if (q && !p.name.toLowerCase().includes(q) && !`${p.ip}:${p.tcp_port}`.includes(q)) {
      return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    const emptyDiv = document.createElement("div");
    emptyDiv.className = "empty-peer-list";
    emptyDiv.innerHTML =
      lanPeers.length === 0
        ? `<div><span class="pulse-dot"></span><b>Đang quét mạng LAN (UDP :9999)...</b></div><div style="margin-top:8px;">Khi có người dùng bật ứng dụng trong mạng LAN, tên của họ sẽ tự động hiện tại đây.</div>`
        : `<div>Không tìm thấy người dùng phù hợp.</div>`;
    convListEl.appendChild(emptyDiv);
    return;
  }

  filtered.forEach((peer) => {
    const item = document.createElement("div");
    const isActive = peer.name === activePeerName;
    item.className = `conv-item${isActive ? " active" : ""}`;
    item.onclick = () => selectPeer(peer.name);

    const lastMsg =
      peer.messages && peer.messages.length > 0
        ? peer.messages[peer.messages.length - 1]
        : null;
    const preview = lastMsg
      ? `${lastMsg.sender === selfName ? "Bạn" : lastMsg.sender}: ${lastMsg.text}`
      : `${peer.ip}:${peer.tcp_port} (${peer.status})`;
    const timeLabel = lastMsg ? lastMsg.time : peer.status === "online" ? "Online" : "Away";
    const badgeHtml =
      peer.unread > 0 ? `<span class="conv-unread-badge">${peer.unread}</span>` : "";

    item.innerHTML = `
      <div class="conv-avatar">
        <img src="${peer.avatar}" alt="${escapeHtml(peer.name)}" />
        <span class="conv-peer-dot ${peer.status}"></span>
      </div>
      <div class="conv-body">
        <div class="conv-top-row">
          <div class="conv-name">${escapeHtml(peer.name)}</div>
          <div class="conv-time">${escapeHtml(timeLabel)}</div>
        </div>
        <div class="conv-bottom-row">
          <div class="conv-preview">${escapeHtml(preview)}</div>
          ${badgeHtml}
        </div>
      </div>
    `;
    convListEl.appendChild(item);
  });
}

function renderActiveChat() {
  const peer = getActivePeer();
  if (!peer) {
    emptyChatScreenEl.classList.remove("hidden");
    activeChatContainerEl.classList.add("hidden");
    updateRightPanelVisibility();
    return;
  }

  emptyChatScreenEl.classList.add("hidden");
  activeChatContainerEl.classList.remove("hidden");
  updateRightPanelVisibility();

  activeHeaderAvatarEl.innerHTML = `<img src="${peer.avatar}" alt="${escapeHtml(peer.name)}" />`;
  activeChatTitleEl.textContent = peer.name;
  activePeerStatusTextEl.textContent =
    peer.status === "online" ? "● Đang hoạt động (Online)" : "● Tạm vắng (Away)";
  activePeerStatusTextEl.className = `peer-status-badge ${peer.status}`;
  activePeerEndpointEl.textContent = `TCP ${peer.ip}:${peer.tcp_port}`;
  messageInputEl.placeholder = `Nhập tin nhắn tới ${peer.name}...`;

  infoAvatarLargeEl.innerHTML = `<img src="${peer.avatar}" alt="${escapeHtml(peer.name)}" />`;
  infoGroupNameEl.textContent = peer.name;
  infoPeerAddressEl.textContent = `Địa chỉ: ${peer.ip}:${peer.tcp_port}`;
  infoPeerStatusEl.textContent = `Trạng thái UDP: ${peer.status.toUpperCase()}`;

  chatMessagesEl.innerHTML = "";

  const pillRow = document.createElement("div");
  pillRow.className = "time-pill-row";
  pillRow.innerHTML = `<span class="time-pill">Kết nối P2P với ${escapeHtml(peer.name)} (${escapeHtml(peer.ip)}:${peer.tcp_port})</span>`;
  chatMessagesEl.appendChild(pillRow);

  const sharedFiles = [];

  (peer.messages || []).forEach((m) => {
    const isOutgoing = m.sender === selfName;
    const row = document.createElement("div");
    row.className = `msg-row ${isOutgoing ? "outgoing" : "incoming"}`;

    const avatarHtml = !isOutgoing
      ? `<div class="msg-sender-avatar"><img src="${peer.avatar}" alt="${escapeHtml(m.sender)}" /></div>`
      : "";
    const senderHtml = !isOutgoing
      ? `<div class="msg-sender-name">${escapeHtml(m.sender)}</div>`
      : "";

    let bodyHtml = "";
    if (m.file) {
      sharedFiles.push(m.file);
      const fileUrl = m.file.url || `/downloads/${encodeURIComponent(m.file.name)}`;
      const imgPreviewHtml = isImageFilename(m.file.name)
        ? `<img class="msg-image-preview" src="${fileUrl}" alt="${escapeHtml(m.file.name)}" data-open-file="${escapeHtml(m.file.name)}" data-open-url="${fileUrl}" title="Bấm để mở ảnh ngay" />`
        : "";
      bodyHtml = `
        <div class="msg-file-box">
          ${imgPreviewHtml}
          <div class="msg-file-card">
            <div class="msg-file-icon">📄</div>
            <div class="msg-file-meta">
              <span class="msg-file-name" title="${escapeHtml(m.file.name)}">${escapeHtml(m.file.name)}</span>
              <span class="msg-file-size">${escapeHtml(m.file.size || "")} • Đã lưu downloads/</span>
            </div>
          </div>
          <div class="msg-file-actions">
            <button type="button" class="file-act-btn" data-open-file="${escapeHtml(m.file.name)}" data-open-url="${fileUrl}">Mở ngay</button>
            <button type="button" class="file-act-btn" data-reveal-file="${escapeHtml(m.file.name)}">Mở thư mục</button>
          </div>
        </div>
      `;
    } else if (m.text === "[Sticker]") {
      bodyHtml = `<img class="sticker-img" src="${STICKER_LAUGH}" alt="Sticker" style="width:104px;height:104px;" />`;
    } else {
      bodyHtml = `<div class="msg-text">${escapeHtml(m.text || "")}</div>`;
    }

    const likesCount = Number(m.likes || 0);
    let reactionHtml = "";
    if (likesCount > 0) {
      reactionHtml = `
        <div class="reaction-cluster">
          <span class="reaction-pill" data-react-id="${m.id}" title="Bấm để thả thêm Like">👍 ${likesCount}</span>
        </div>
      `;
    } else {
      reactionHtml = `<button type="button" class="reaction-hover-btn" data-react-id="${m.id}" title="Thả Like">👍</button>`;
    }

    row.innerHTML = `
      ${avatarHtml}
      <div class="msg-bubble">
        ${senderHtml}
        ${bodyHtml}
        <div class="msg-time">${escapeHtml(m.time || "")}</div>
        ${reactionHtml}
      </div>
    `;

    row.querySelectorAll("[data-react-id]").forEach((btn) => {
      btn.onclick = async () => {
        await fetch("/api/react", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: peer.name, msgId: m.id })
        });
        await pollBackendState(true);
      };
    });

    row.querySelectorAll("[data-open-file]").forEach((btn) => {
      btn.onclick = () => {
        openFileImmediately(
          btn.getAttribute("data-open-file"),
          btn.getAttribute("data-open-url")
        );
      };
    });

    row.querySelectorAll("[data-reveal-file]").forEach((btn) => {
      btn.onclick = () => {
        revealFileInDownloads(btn.getAttribute("data-reveal-file"));
      };
    });

    chatMessagesEl.appendChild(row);
  });

  /* Render shared files list in Right Info Panel */
  sharedFilesListEl.innerHTML = "";
  if (sharedFiles.length === 0) {
    sharedFilesListEl.innerHTML = `<div class="empty-files-note">Chưa có file nào trong phiên này</div>`;
  } else {
    sharedFiles.forEach((f) => {
      const fUrl = f.url || `/downloads/${encodeURIComponent(f.name)}`;
      const item = document.createElement("div");
      item.className = "shared-file-item";
      item.innerHTML = `
        <span class="shared-file-name" title="${escapeHtml(f.name)}">📎 ${escapeHtml(f.name)}</span>
        <button type="button" class="file-act-btn" data-open-file="${escapeHtml(f.name)}" data-open-url="${fUrl}">Mở</button>
      `;
      item.querySelector("[data-open-file]").onclick = () =>
        openFileImmediately(f.name, fUrl);
      sharedFilesListEl.appendChild(item);
    });
  }

  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

async function selectPeer(peerName) {
  activePeerName = peerName;
  try {
    await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: peerName })
    });
  } catch (_) {}
  await pollBackendState(true);
  messageInputEl.focus();
}

/* Composer Input & Send */
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
  const peer = getActivePeer();
  if (!peer) return;

  const raw = messageInputEl.value.trim();
  const textToSend = raw || "👍";
  messageInputEl.value = "";
  sendOrLikeBtnEl.textContent = "👍";
  sendOrLikeBtnEl.classList.remove("send-mode");

  try {
    await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: peer.name, text: textToSend })
    });
    await pollBackendState(true);
  } catch (_) {}
});

/* Sticker Send */
document.getElementById("stickerBtn").addEventListener("click", async () => {
  const peer = getActivePeer();
  if (!peer) return;
  try {
    await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: peer.name, text: "[Sticker]" })
    });
    await pollBackendState(true);
  } catch (_) {}
});

/* File Transfer via Paperclip / Image / Quick Action Buttons */
const hiddenFileInput = document.getElementById("hiddenFileInput");
document.getElementById("attachFileBtn").addEventListener("click", () => hiddenFileInput.click());
document.getElementById("imageBtn").addEventListener("click", () => hiddenFileInput.click());
document.getElementById("qaSendFileBtn").addEventListener("click", () => hiddenFileInput.click());

hiddenFileInput.addEventListener("change", async () => {
  const file = hiddenFileInput.files[0];
  const peer = getActivePeer();
  if (!file || !peer) return;
  hiddenFileInput.value = "";

  const formData = new FormData();
  formData.append("target", peer.name);
  formData.append("file", file);

  transferBarEl.classList.remove("hidden");
  transferLabelEl.textContent = `Đang gửi ${file.name}...`;
  transferFillEl.style.width = "35%";
  transferPctEl.textContent = "35%";

  try {
    await fetch("/api/send_file", {
      method: "POST",
      body: formData
    });
    transferFillEl.style.width = "100%";
    transferPctEl.textContent = "100%";
    setTimeout(() => transferBarEl.classList.add("hidden"), 700);
    await pollBackendState(true);
  } catch (_) {
    transferBarEl.classList.add("hidden");
  }
});

/* Leave current chat (/leave) */
async function leaveCurrentChat() {
  activePeerName = null;
  try {
    await fetch("/api/leave", { method: "POST" });
  } catch (_) {}
  renderConversationList();
  renderActiveChat();
}

document.getElementById("leaveChatBtn").addEventListener("click", leaveCurrentChat);
document.getElementById("qaLeaveBtn").addEventListener("click", leaveCurrentChat);

/* Open downloads/ folder */
async function openDownloadsFolder() {
  await revealFileInDownloads(".gitkeep");
}
document.getElementById("openDownloadsFolderBtn").addEventListener("click", openDownloadsFolder);
document.getElementById("qaOpenDownloadsBtn").addEventListener("click", openDownloadsFolder);

/* Right Panel Collapse / Expand & Drag-to-Resize */
toggleRightPanelBtnEl.addEventListener("click", () => {
  infoPanelOpen = !infoPanelOpen;
  updateRightPanelVisibility();
});

document.getElementById("collapseInfoBtn").addEventListener("click", () => {
  infoPanelOpen = false;
  updateRightPanelVisibility();
});

infoPullTabEl.addEventListener("click", () => {
  infoPanelOpen = true;
  if (infoSidebarEl.offsetWidth < 220) {
    infoSidebarEl.style.width = "320px";
  }
  updateRightPanelVisibility();
});

let isResizingInfo = false;
infoResizeHandleEl.addEventListener("mousedown", (e) => {
  e.preventDefault();
  isResizingInfo = true;
  infoSidebarEl.classList.add("dragging");
});

window.addEventListener("mousemove", (e) => {
  if (!isResizingInfo) return;
  const newWidth = window.innerWidth - e.clientX;
  if (newWidth < 130) {
    infoPanelOpen = false;
    isResizingInfo = false;
    infoSidebarEl.classList.remove("dragging");
    updateRightPanelVisibility();
  } else if (newWidth >= 220 && newWidth <= 520) {
    infoSidebarEl.style.width = `${newWidth}px`;
  }
});

window.addEventListener("mouseup", () => {
  if (isResizingInfo) {
    isResizingInfo = false;
    infoSidebarEl.classList.remove("dragging");
  }
});

/* Filter Tabs & Search */
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

/* Toggle UDP Online/Away status */
document.getElementById("toggleStatusBtn").addEventListener("click", async () => {
  myStatus = myStatus === "online" ? "away" : "online";
  document.getElementById("myStatusDot").className = `status-dot ${myStatus}`;
  try {
    await fetch("/api/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: myStatus })
    });
  } catch (_) {}
});

/* Poll Live State from Python P2P Bridge */
let lastSnapshotJson = "";

async function pollBackendState(forceRender = false) {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();

    selfName = data.selfName || "Tôi";
    document.getElementById("windowTitle").textContent =
      `Zalo - ${selfName} (TCP :${data.tcpPort} | UDP :${data.udpPort})`;
    document.getElementById("myAvatarImg").src = makePeerAvatar(selfName);
    document.getElementById("lanScanBadge").textContent = `UDP :${data.udpPort}`;

    if (data.transfer && data.transfer.active) {
      transferBarEl.classList.remove("hidden");
      transferLabelEl.textContent = data.transfer.label;
      transferFillEl.style.width = `${data.transfer.pct}%`;
      transferPctEl.textContent = `${data.transfer.pct}%`;
    } else if (data.transfer && !data.transfer.active) {
      transferBarEl.classList.add("hidden");
    }

    const updatedPeers = (data.peers || []).map((p) => ({
      name: p.name,
      ip: p.ip,
      tcp_port: p.tcp_port,
      status: p.status || "online",
      avatar: makePeerAvatar(p.name),
      unread:
        activePeerName === p.name
          ? 0
          : (data.unreads && data.unreads[p.name]) || 0,
      messages: (data.histories && data.histories[p.name]) || []
    }));

    // Auto-close active chat if the peer went offline and has no messages
    if (
      activePeerName &&
      !updatedPeers.some((p) => p.name === activePeerName)
    ) {
      activePeerName = null;
    }

    const snapStr = JSON.stringify({
      activePeerName,
      updatedPeers
    });

    if (forceRender || snapStr !== lastSnapshotJson) {
      lastSnapshotJson = snapStr;
      lanPeers = updatedPeers;
      renderConversationList();
      renderActiveChat();
    }
  } catch (_) {}
}

renderConversationList();
renderActiveChat();
setInterval(() => pollBackendState(false), 800);
pollBackendState(true);
