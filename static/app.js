'use strict';
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
// Back/forward cache must not restore an obsolete signed-in identity after logout.
window.addEventListener('pageshow', event => {
  if (event.persisted && document.body.dataset.userId) location.reload();
});
// Keep stored UTC timestamps accurate, but display them in the reader’s locale.
$$('time[datetime]').forEach(time => {
  const date = new Date(time.dateTime);
  if (Number.isNaN(date.getTime())) return;
  time.textContent = new Intl.DateTimeFormat(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  }).format(date);
  time.title = new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'long' }).format(date);
});
let toastTimer;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4000);
}
function showLabFlags(header) {
  const notice = $('#lab-discoveries');
  if (!notice || !header) return;
  const list = $('.lab-flag-list', notice);
  header.split(',').map(flag => flag.trim()).forEach(flag => {
    if (!/^COMMON\{[a-z0-9_]+\}$/.test(flag)) return;
    if ($$('code', list).some(code => code.textContent === flag)) return;
    const item = document.createElement('li');
    const code = document.createElement('code');
    code.textContent = flag;
    item.append(code);
    list.append(item);
  });
  notice.hidden = !list.children.length;
}
async function api(path, method = 'GET', data) {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': $('meta[name="csrf-token"]').content },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  const result = await response.json().catch(() => ({}));
  showLabFlags(response.headers.get('X-Lab-Flags'));
  if (response.status === 401) {
    location.assign('/login');
    throw new Error('Your session ended. Sign in again.');
  }
  if (!response.ok) throw new Error(result.error || 'Couldn’t finish that. Refresh and try again.');
  return result;
}
function onForm(selector, handler) {
  const form = $(selector);
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = $('button[type="submit"], button', form);
    if (form.getAttribute('aria-busy') === 'true') return;
    form.setAttribute('aria-busy', 'true');
    if (button) button.disabled = true;
    const originalChildren = button && [...button.childNodes];
    if (button && form.dataset.pendingLabel) button.textContent = form.dataset.pendingLabel;
    try { await handler(form, Object.fromEntries(new FormData(form))); }
    catch (error) { toast(error.message); }
    finally {
      form.removeAttribute('aria-busy');
      if (button) {
        button.disabled = false;
        if (form.dataset.pendingLabel) button.replaceChildren(...originalChildren);
      }
    }
  });
}
onForm('#compose-form', async (form, data) => {
  await api('/api/posts', 'POST', data);
  // Non-public posts belong on your own profile, not in the public feed.
  if (data.visibility !== 'public') location.href = '/people/' + document.querySelector('.account small').textContent.slice(1);
  else location.reload();
});
onForm('#settings-form', async (form, data) => {
  const result = await api(`/api/users/${form.dataset.id}`, 'PATCH', data);
  const user = result.user;
  if (!user || !Number.isInteger(user.id)) {
    throw new Error('The server did not identify the updated account. Refresh to verify your changes.');
  }
  if (user.id !== Number(form.dataset.id) || user.id !== Number(document.body.dataset.userId)) {
    toast(`Changes saved to @${user.username} (account #${user.id}), not your signed-in account.`);
    return;
  }
  // Apply server-confirmed values, not the submitted form or another user's response.
  ['name', 'bio', 'location', 'email'].forEach(key => {
    if (typeof user[key] === 'string') form.elements.namedItem(key).value = user[key];
  });
  $$('[data-current-user-name]').forEach(label => { label.textContent = user.name; });
  const words = user.name.trim().split(/\s+/);
  const initials = Array.from(words[0])[0] + Array.from(words[words.length - 1])[0];
  $$('.account .avatar, .top-avatar .avatar, .settings-avatar .avatar').forEach(avatar => {
    avatar.textContent = initials;
  });
  $('.top-avatar')?.setAttribute('aria-label', `Your profile: ${user.name}`);
  toast(result.changed_fields?.length
    ? `Changes saved for @${user.username} (account #${user.id}).`
    : `No changes to save for @${user.username} (account #${user.id}).`);
});
function authorLabel(author) {
  return author.username ? `${author.name} · @${author.username}` : author.name;
}
$$('[data-action]').forEach(button => button.addEventListener('click', async () => {
  button.disabled = true;
  try {
    const result = await api(`/api/posts/${button.dataset.id}/${button.dataset.action}`, 'POST', {});
    button.classList.toggle('selected', result.active);
    button.setAttribute('aria-pressed', String(result.active));
    if (button.dataset.action === 'like') $('span', button).textContent = result.count;
    else toast(result.active ? 'Saved for another day.' : 'Removed from saved posts.');
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}));
function drawComments(panel, comments) {
  const list = $('.comment-list', panel);
  list.replaceChildren();
  if (!comments.length) {
    const p = document.createElement('p'); p.textContent = 'Start the conversation.'; list.append(p);
  }
  comments.forEach(comment => {
    const p = document.createElement('p');
    const name = document.createElement('strong'); name.textContent = authorLabel(comment);
    p.append(name, document.createTextNode(comment.body)); list.append(p);
  });
}
$$('.show-comments').forEach(button => button.addEventListener('click', async () => {
  const panel = $(`[data-comments="${button.dataset.id}"]`);
  if (!panel.hidden) { panel.hidden = true; return; }
  try { drawComments(panel, await api(`/api/posts/${button.dataset.id}/comments`)); panel.hidden = false; }
  catch (error) { toast(error.message); }
}));
$$('.comment-form').forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('button', form); button.disabled = true;
  try {
    const comments = await api(`/api/posts/${form.dataset.id}/comments`, 'POST', Object.fromEntries(new FormData(form)));
    drawComments(form.parentElement, comments); form.reset();
    const count = $(`.show-comments[data-id="${form.dataset.id}"] > span`);
    count.textContent = `${comments.length} ${comments.length === 1 ? 'comment' : 'comments'}`;
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}));
$$('.delete-post').forEach(button => button.addEventListener('click', async () => {
  if (!confirm('Delete this post? This can’t be undone.')) return;
  try { await api(`/api/posts/${button.dataset.id}`, 'DELETE'); $(`#post-${button.dataset.id}`).remove(); toast('Post deleted.'); }
  catch (error) { toast(error.message); }
}));
let activeConversation;
let conversationRequest = 0;
async function loadConversation(id) {
  const requestId = ++conversationRequest;
  activeConversation = undefined;
  $('#conversation-content').hidden = true;
  $('#conversation-empty').hidden = false;
  const thread = await api(`/api/conversations/${id}`);
  if (requestId !== conversationRequest) return;
  activeConversation = id;
  $('#conversation-empty').hidden = true;
  $('#conversation-content').hidden = false;
  $('#conversation-title').textContent = thread.subject;
  $$('.thread').forEach(button => button.classList.toggle('active', button.dataset.id === String(id)));
  const list = $('#message-list'); list.replaceChildren();
  thread.messages.forEach(message => {
    const bubble = document.createElement('div'); bubble.className = 'message';
    const name = document.createElement('strong'); name.textContent = authorLabel(message);
    const text = document.createElement('p'); text.textContent = message.body;
    bubble.append(name, text); list.append(bubble);
  });
  list.scrollTop = list.scrollHeight;
}
$$('.thread').forEach(button => button.addEventListener('click', () => loadConversation(button.dataset.id).catch(error => toast(error.message))));
onForm('#message-form', async (form, data) => {
  const id = activeConversation;
  if (id === undefined) return;
  await api(`/api/conversations/${id}`, 'POST', data);
  if (activeConversation === id) {
    form.reset();
    await loadConversation(id);
  }
});
onForm('#search-form', async (form) => {
  const results = $('#search-results');
  const users = await api('/api/search?q=' + encodeURIComponent($('#search').value));
  results.replaceChildren();
  users.forEach(user => {
    const link = document.createElement('a'); link.href = '/people/' + encodeURIComponent(user.username);
    link.textContent = `${user.name} · @${user.username}`; results.append(link);
  });
  if (!users.length) { const p = document.createElement('p'); p.textContent = 'No neighbors found. Try another name.'; results.append(p); }
  results.hidden = false;
});
document.addEventListener('click', event => { if (!event.target.closest('.search') && $('#search-results')) $('#search-results').hidden = true; });
document.addEventListener('keydown', event => { if (event.key === 'Escape' && $('#search-results')) $('#search-results').hidden = true; });
$$('.resolve-report').forEach(button => button.addEventListener('click', async () => {
  try { await api(`/api/staff/reports/${button.dataset.id}/resolve`, 'POST', {}); location.reload(); }
  catch (error) { toast(error.message); }
}));
