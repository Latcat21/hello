document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page || "main";

  const authForm = document.getElementById("auth-form");
  const nameInput = document.getElementById("auth-name");
  const passInput = document.getElementById("auth-pass");
  const authBadge = document.getElementById("auth-badge");
  const authStatus = document.getElementById("auth-status");
  const signOutBtn = document.getElementById("sign-out-btn");
  const authButtons = authForm ? authForm.querySelectorAll("[data-action]") : [];
  const authLinks = document.querySelectorAll(".auth-link");
  const deleteMessagesBtn = document.getElementById("delete-messages-btn");
  const deleteStatus = document.getElementById("delete-status");
  let currentUser = null;
  let hasOwnMessages = false;
  const imageFileInput = document.getElementById("image-file");
  const linkUrlInput = document.getElementById("link-url");
  const passConfirmInput = document.getElementById("auth-pass-confirm");
  const adminLinks = document.querySelectorAll(".admin-link");
  const getYouTubeId = (text = "") => {
    const match = text.match(
      /(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([A-Za-z0-9_-]{11})/,
    );
    return match ? match[1] : null;
  };
  const normalizeLink = (url) => {
    if (!url) return null;
    try {
      const parsed = new URL(url.trim(), window.location.origin);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
      return parsed.toString();
    } catch {
      return null;
    }
  };

  const noteForm = document.getElementById("note-form");
  const noteInput = document.getElementById("note-input");
  const noteOwner = document.getElementById("note-owner");
  const saveNoteBtn = document.getElementById("save-note-btn");
  const noteAlert = document.getElementById("note-alert");
  const noteFeed = document.getElementById("note-feed");

  const setStatus = (msg, isError = false) => {
    if (!authStatus) return;
    authStatus.textContent = msg;
    authStatus.classList.toggle("text-danger", isError);
    authStatus.classList.toggle("text-secondary", !isError);
  };

  const renderFeed = (notes = []) => {
    if (!noteFeed) return;
    noteFeed.innerHTML = "";
    if (!notes.length) {
      noteFeed.innerHTML =
        '<li class="list-group-item bg-transparent text-secondary">No notes yet.</li>';
      hasOwnMessages = false;
      updateDeleteButton();
      return;
    }
    hasOwnMessages = false;
    notes.forEach((item) => {
      const li = document.createElement("li");
      li.className =
        "list-group-item bg-transparent d-flex flex-column flex-md-row justify-content-between align-items-start";
      const name = document.createElement("div");
      const time = item.created_at
        ? new Date(item.created_at).toLocaleTimeString()
        : "";
      name.innerHTML = `<strong class="text-white">${item.username}</strong>${
        time ? `<div class="text-white-50 small">${time}</div>` : ""
      }`;
      const text = document.createElement("div");
      text.className = "text-white ms-md-3 mt-2 mt-md-0 flex-grow-1";
      text.textContent = item.note || "(empty)";
      const ytId = getYouTubeId(item.note || "");
      if (ytId) {
        const preview = document.createElement("div");
        preview.className = "ratio ratio-16x9 mt-2";
        const iframe = document.createElement("iframe");
        iframe.src = `https://www.youtube.com/embed/${ytId}`;
        iframe.title = "YouTube preview";
        iframe.allow =
          "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
        iframe.allowFullscreen = true;
        preview.appendChild(iframe);
        text.appendChild(preview);
      }
      if (item.image_url) {
        const imgWrap = document.createElement("div");
        imgWrap.className = "mt-2";
        const img = document.createElement("img");
        img.src = item.image_url;
        img.alt = "Shared image";
        img.className = "img-fluid rounded";
        imgWrap.appendChild(img);
        text.appendChild(imgWrap);
      }
      const linkUrl = normalizeLink(item.link_url);
      if (linkUrl) {
        const linkCard = document.createElement("div");
        linkCard.className =
          "mt-2 p-2 border border-secondary-subtle rounded bg-dark bg-opacity-25";
        const link = document.createElement("a");
        link.href = linkUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "text-white text-decoration-underline";
        link.textContent = linkUrl;
        linkCard.appendChild(link);
        const frame = document.createElement("iframe");
        frame.src = linkUrl;
        frame.className = "w-100 rounded border mt-2";
        frame.loading = "lazy";
        frame.sandbox = "allow-same-origin allow-scripts allow-popups";
        frame.style.minHeight = "200px";
        linkCard.appendChild(frame);
        text.appendChild(linkCard);
      }
      if (item.link_url) {
        const linkCard = document.createElement("div");
        linkCard.className = "mt-2 p-2 border border-secondary-subtle rounded bg-dark bg-opacity-25";
        const link = document.createElement("a");
        link.href = item.link_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "text-white text-decoration-underline";
        link.textContent = item.link_url;
        linkCard.appendChild(link);
        text.appendChild(linkCard);
      }
      const actions = document.createElement("div");
      actions.className = "ms-md-3 mt-2 mt-md-0";
      if (currentUser && item.username === currentUser) {
        hasOwnMessages = true;
        const delBtn = document.createElement("button");
        delBtn.className = "btn btn-sm btn-outline-danger";
        delBtn.textContent = "Delete";
        delBtn.addEventListener("click", () => deleteMessage(item.id));
        actions.appendChild(delBtn);
      }
      li.appendChild(name);
      li.appendChild(text);
      if (actions.children.length) {
        li.appendChild(actions);
      }
      noteFeed.appendChild(li);
    });
    updateDeleteButton();
  };

  const refreshUI = (user) => {
    const signedIn = Boolean(user);
    currentUser = signedIn ? user.username : null;
    if (authBadge) authBadge.textContent = signedIn ? user.username : "Guest";
    if (noteOwner) noteOwner.textContent = signedIn ? user.username : "Guest";
    if (signOutBtn) {
      signOutBtn.disabled = !signedIn;
      signOutBtn.classList.toggle("d-none", !signedIn && page === "main");
    }
    updateDeleteButton();
    authLinks.forEach((link) => {
      if (!(link instanceof HTMLElement)) return;
      link.classList.toggle("d-none", signedIn);
    });
    adminLinks.forEach((link) => {
      if (!(link instanceof HTMLElement)) return;
      link.classList.toggle("d-none", !(signedIn && user?.is_admin));
    });
    if (saveNoteBtn) saveNoteBtn.disabled = !signedIn;
    if (noteInput) noteInput.disabled = !signedIn;
    if (imageFileInput) imageFileInput.disabled = !signedIn;
    if (linkUrlInput) linkUrlInput.disabled = !signedIn;
    if (signedIn && nameInput) {
      nameInput.value = user.username;
    } else if (nameInput) {
      nameInput.value = "";
    }
    if (passInput) passInput.value = "";
    if (passConfirmInput) passConfirmInput.value = "";
    setStatus(
      signedIn ? `Signed in as ${user.username}.` : "No one is signed in.",
    );
    if (!signedIn && noteInput) noteInput.value = "";
  };

  const showSaved = () => {
    if (!noteAlert) return;
    noteAlert.classList.remove("d-none");
    setTimeout(() => {
      noteAlert.classList.add("d-none");
    }, 1500);
  };

  const fetchJSON = async (url, options = {}) => {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Request failed");
    }
    return res.json();
  };

  const uploadImage = async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/upload_image", {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Image upload failed");
    }
    return res.json();
  };

  const getMe = async () => {
    try {
      const data = await fetchJSON("/api/me", { method: "GET" });
      refreshUI(data.user || null);
      if (data.user && typeof data.note === "string" && noteInput) {
        noteInput.value = data.note;
      }
      if (noteFeed) {
        await fetchNotes();
      }
      if ((page === "auth" || page === "signup") && data.user) {
        setTimeout(() => {
          window.location.href = "/chat";
        }, 150);
      }
      if (page === "account" && !data.user) {
        setTimeout(() => {
          window.location.href = "/auth";
        }, 150);
      }
    } catch (err) {
      setStatus(err.message, true);
    }
  };

  const fetchNotes = async () => {
    if (!noteFeed) return;
    try {
      const data = await fetchJSON("/api/notes", { method: "GET" });
      renderFeed(data.notes || []);
    } catch (err) {
      renderFeed([]);
      setStatus("Could not load notes.", true);
    }
  };

  const handleAuth = async (action) => {
    if (!nameInput || !passInput) return;
    const username = nameInput.value.trim();
    const password = passInput.value;
    const confirm = passConfirmInput ? passConfirmInput.value : "";
    if (!username || !password) {
      setStatus("Username and password required.", true);
      return;
    }
    if (action === "signup") {
      if (password.length < 8 || !/\d/.test(password)) {
        setStatus("Password must be at least 8 characters and include a number.", true);
        return;
      }
      if (passConfirmInput && password !== confirm) {
        setStatus("Passwords do not match.", true);
        return;
      }
    }
    try {
      const data = await fetchJSON(`/api/${action}`, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      refreshUI(data.user);
      if (noteInput) noteInput.value = data.note || "";
      setStatus(
        action === "signup"
          ? `Account created. Signed in as ${data.user.username}.`
          : `Signed in as ${data.user.username}.`,
      );
      if (noteFeed) await fetchNotes();
      if (page === "auth" || page === "signup") {
        setTimeout(() => {
          window.location.href = "/chat";
        }, 300);
      }
    } catch (err) {
      setStatus(err.message, true);
    }
  };

  const saveNote = async () => {
    try {
      let imageUrl = null;
      const file = imageFileInput?.files?.[0];
      if (file) {
        const uploaded = await uploadImage(file);
        imageUrl = uploaded.url || null;
      }
      await fetchJSON("/api/note", {
        method: "POST",
        body: JSON.stringify({
          note: noteInput.value,
          image_url: imageUrl,
          link_url: linkUrlInput ? normalizeLink(linkUrlInput.value) : null,
        }),
      });
      showSaved();
      setStatus("Note saved.");
      await fetchNotes();
      if (imageFileInput) imageFileInput.value = "";
      if (linkUrlInput) linkUrlInput.value = "";
    } catch (err) {
      setStatus(err.message, true);
    }
  };

  const deleteMessages = async () => {
    if (deleteStatus) deleteStatus.textContent = "";
    try {
      await fetchJSON("/api/messages/delete", { method: "POST" });
      if (deleteStatus) deleteStatus.textContent = "Messages deleted.";
      if (noteFeed) await fetchNotes();
      if (noteInput) noteInput.value = "";
    } catch (err) {
      if (deleteStatus) deleteStatus.textContent = err.message;
      setStatus(err.message, true);
    }
  };

  const deleteMessage = async (id) => {
    if (deleteStatus) deleteStatus.textContent = "";
    try {
      await fetchJSON("/api/messages/delete_one", {
        method: "POST",
        body: JSON.stringify({ id }),
      });
      if (deleteStatus) deleteStatus.textContent = "Message deleted.";
      if (noteFeed) await fetchNotes();
    } catch (err) {
      if (deleteStatus) deleteStatus.textContent = err.message;
      setStatus(err.message, true);
    }
  };

  authButtons.forEach((btn) => {
    btn.addEventListener("click", () => handleAuth(btn.dataset.action));
  });

  if (signOutBtn) {
    signOutBtn.addEventListener("click", async () => {
      try {
        await fetchJSON("/api/logout", { method: "POST" });
        refreshUI(null);
        if (noteFeed) await fetchNotes();
        if (page === "chat") {
          setTimeout(() => {
            window.location.href = "/";
          }, 300);
        }
      } catch (err) {
        setStatus(err.message, true);
      }
    });
  }

  if (noteForm) {
    noteForm.addEventListener("submit", (event) => {
      event.preventDefault();
      saveNote();
    });
  }

  if (deleteMessagesBtn) {
    deleteMessagesBtn.addEventListener("click", deleteMessages);
  }

  const updateDeleteButton = () => {
    if (!deleteMessagesBtn) return;
    const show = Boolean(currentUser && hasOwnMessages);
    deleteMessagesBtn.disabled = !show;
    deleteMessagesBtn.classList.toggle("d-none", !show);
  };

  getMe();
});
