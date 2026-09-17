const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/+$/, '');

export function getAuthToken() {
  return localStorage.getItem('mukku_token');
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('mukku_token', token);
  } else {
    localStorage.removeItem('mukku_token');
  }
}

export function getGuestId() {
  let guestId = localStorage.getItem('mukku_guest_id');
  if (!guestId) {
    guestId = 'guest_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now().toString(36);
    localStorage.setItem('mukku_guest_id', guestId);
  }
  return guestId;
}

async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const guestId = getGuestId();
  const headers = {
    'X-Guest-Id': guestId,
    ...(options.headers || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed (${response.status})`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// Auth API
export const apiAuth = {
  getGuestToken: async () => {
    const res = await request('/auth/guest-token');
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },
  login: async (data) => {
    const res = await request('/auth/login', { method: 'POST', body: JSON.stringify(data) });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },
  register: async (data) => {
    const res = await request('/auth/register', { method: 'POST', body: JSON.stringify(data) });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },
  getMe: () => request('/auth/me'),
  logout: () => {
    setAuthToken(null);
  },
};

// Ollama API
export const apiOllama = {
  getStatus: () => request('/ollama/status'),
  getModels: () => request('/ollama/models'),
};

// Conversations API
export const apiConversations = {
  list: (search = '') => request(`/conversations${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  search: (query) => request(`/conversations/search?q=${encodeURIComponent(query)}`),
  get: (id) => request(`/conversations/${id}`),
  create: (data) => request('/conversations', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/conversations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),
  deleteAll: () => request('/conversations', { method: 'DELETE' }),
  clear: (id) => request(`/conversations/${id}/clear`, { method: 'POST' }),

  // Messages API
  getMessages: (id, { limit = 50, before = null } = {}) => {
    let url = `/conversations/${id}/messages?limit=${limit}`;
    if (before) {
      url += `&before=${encodeURIComponent(before)}`;
    }
    return request(url);
  },
  createMessage: (convId, data) => request(`/conversations/${convId}/messages`, { method: 'POST', body: JSON.stringify(data) }),
  deleteMessage: (convId, msgId) => request(`/conversations/${convId}/messages/${msgId}`, { method: 'DELETE' }),

  // Import / Export
  exportOne: (id) => request(`/conversations/${id}/export`),
  exportAll: () => request('/conversations/export'),
  importConversations: (conversationsList) => request('/conversations/import', { method: 'POST', body: JSON.stringify({ conversations: conversationsList }) }),
};

// Memory API
export const apiMemory = {
  list: (activeOnly = false) => request(`/memory?active_only=${activeOnly}`),
  create: (data) => request('/memory', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/memory/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id) => request(`/memory/${id}`, { method: 'DELETE' }),
};

// Documents API
export const apiDocuments = {
  list: () => request('/documents'),
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/documents', { method: 'POST', body: formData });
  },
  delete: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  search: (query) => {
    const formData = new FormData();
    formData.append('query', query);
    return request('/documents/search', { method: 'POST', body: formData });
  },
};

// Settings API
export const apiSettings = {
  get: () => request('/settings'),
  update: (data) => request('/settings', { method: 'PATCH', body: JSON.stringify(data) }),
};

// SSE Chat Streaming Reader
export async function streamChatResponse({
  endpoint = '/chat/stream',
  payload,
  onToken,
  onToolStart,
  onToolEnd,
  onCitations,
  onConversationCreated,
  onTitleUpdated,
  onDone,
  onError,
  signal,
}) {
  const token = getAuthToken();
  const guestId = getGuestId();
  const headers = {
    'Content-Type': 'application/json',
    'X-Guest-Id': guestId,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      let errMsg = `Server returned ${response.status}`;
      try {
        const errJson = await response.json();
        errMsg = errJson.detail || errJson.error || errMsg;
      } catch {}
      throw new Error(errMsg);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        const jsonStr = trimmed.slice(6);
        try {
          const data = JSON.parse(jsonStr);
          switch (data.event) {
            case 'token':
              if (onToken) onToken(data.content);
              break;
            case 'tool_start':
              if (onToolStart) onToolStart(data.tool, data.status);
              break;
            case 'tool_end':
              if (onToolEnd) onToolEnd(data.tool, data.status);
              break;
            case 'citations':
              if (onCitations) onCitations(data.citations);
              break;
            case 'conversation':
              if (onConversationCreated) onConversationCreated(data.conversation_id);
              break;
            case 'title_updated':
              if (onTitleUpdated) onTitleUpdated(data.title);
              break;
            case 'done':
              if (onDone) onDone(data.message_id, data.status);
              break;
            case 'error':
              if (onError) onError(new Error(data.message));
              break;
          }
        } catch (e) {
          console.warn('Error parsing SSE event chunk:', e);
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Stream aborted by user');
    } else {
      if (onError) onError(err);
    }
  }
}
