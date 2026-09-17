/**
 * MukkuAICache - High-performance client-side IndexedDB caching layer.
 * Provides instant startup, offline chat reading, and resilience across refreshes/disconnects.
 */

const DB_NAME = 'MukkuAICache';
const DB_VERSION = 1;

let dbPromise = null;

export function getDB() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      if (typeof window === 'undefined' || !window.indexedDB) {
        return reject(new Error('IndexedDB is not supported in this environment'));
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // Conversations store
        if (!db.objectStoreNames.contains('conversations')) {
          const convStore = db.createObjectStore('conversations', { keyPath: 'id' });
          convStore.createIndex('user_id', 'user_id', { unique: false });
          convStore.createIndex('updated_at', 'updated_at', { unique: false });
        }

        // Messages store
        if (!db.objectStoreNames.contains('messages')) {
          const msgStore = db.createObjectStore('messages', { keyPath: 'id' });
          msgStore.createIndex('conversation_id', 'conversation_id', { unique: false });
          msgStore.createIndex('created_at', 'created_at', { unique: false });
          msgStore.createIndex('sync_status', 'sync_status', { unique: false });
        }

        // Offline queue store
        if (!db.objectStoreNames.contains('offline_queue')) {
          const queueStore = db.createObjectStore('offline_queue', { keyPath: 'id' });
          queueStore.createIndex('created_at', 'created_at', { unique: false });
        }

        // Metadata store
        if (!db.objectStoreNames.contains('meta')) {
          db.createObjectStore('meta', { keyPath: 'key' });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  return dbPromise;
}

/**
 * Cache conversations list in IndexedDB
 */
export async function cacheConversations(conversations) {
  try {
    const db = await getDB();
    const tx = db.transaction('conversations', 'readwrite');
    const store = tx.objectStore('conversations');
    for (const c of conversations) {
      store.put(c);
    }
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to cache conversations to IndexedDB:', err);
  }
}

/**
 * Get all cached conversations, sorted by updated_at descending
 */
export async function getCachedConversations() {
  try {
    const db = await getDB();
    const tx = db.transaction('conversations', 'readonly');
    const store = tx.objectStore('conversations');
    const request = store.getAll();

    return new Promise((resolve, reject) => {
      request.onsuccess = () => {
        const list = request.result || [];
        list.sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0));
        resolve(list);
      };
      request.onerror = () => reject(request.error);
    });
  } catch (err) {
    console.warn('Failed to retrieve cached conversations:', err);
    return [];
  }
}

/**
 * Save or update a single conversation in cache
 */
export async function saveCachedConversation(conversation) {
  try {
    const db = await getDB();
    const tx = db.transaction('conversations', 'readwrite');
    tx.objectStore('conversations').put(conversation);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to save conversation to IndexedDB:', err);
  }
}

/**
 * Delete a conversation and all its associated messages from cache
 */
export async function deleteCachedConversation(conversationId) {
  try {
    const db = await getDB();
    const tx = db.transaction(['conversations', 'messages'], 'readwrite');
    const convStore = tx.objectStore('conversations');
    const msgStore = tx.objectStore('messages');

    convStore.delete(conversationId);

    const index = msgStore.index('conversation_id');
    const request = index.getAllKeys(conversationId);
    request.onsuccess = () => {
      const keys = request.result || [];
      for (const k of keys) {
        msgStore.delete(k);
      }
    };

    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to delete conversation from IndexedDB:', err);
  }
}

/**
 * Clear all cached conversations and messages
 */
export async function clearAllCache() {
  try {
    const db = await getDB();
    const tx = db.transaction(['conversations', 'messages', 'offline_queue'], 'readwrite');
    tx.objectStore('conversations').clear();
    tx.objectStore('messages').clear();
    tx.objectStore('offline_queue').clear();
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to clear cache:', err);
  }
}

/**
 * Cache multiple messages
 */
export async function cacheMessages(messages) {
  if (!messages || !messages.length) return;
  try {
    const db = await getDB();
    const tx = db.transaction('messages', 'readwrite');
    const store = tx.objectStore('messages');
    for (const m of messages) {
      store.put(m);
    }
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to cache messages to IndexedDB:', err);
  }
}

/**
 * Get cached messages for a specific conversation, sorted chronologically
 */
export async function getCachedMessages(conversationId) {
  if (!conversationId) return [];
  try {
    const db = await getDB();
    const tx = db.transaction('messages', 'readonly');
    const index = tx.objectStore('messages').index('conversation_id');
    const request = index.getAll(conversationId);

    return new Promise((resolve, reject) => {
      request.onsuccess = () => {
        const msgs = request.result || [];
        msgs.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0));
        resolve(msgs);
      };
      request.onerror = () => reject(request.error);
    });
  } catch (err) {
    console.warn('Failed to get cached messages from IndexedDB:', err);
    return [];
  }
}

/**
 * Put or update a single message
 */
export async function saveCachedMessage(message) {
  try {
    const db = await getDB();
    const tx = db.transaction('messages', 'readwrite');
    tx.objectStore('messages').put(message);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to save message to IndexedDB:', err);
  }
}

/**
 * Update specific fields of a cached message
 */
export async function updateCachedMessage(messageId, updates) {
  try {
    const db = await getDB();
    const tx = db.transaction('messages', 'readwrite');
    const store = tx.objectStore('messages');
    const req = store.get(messageId);

    return new Promise((resolve, reject) => {
      req.onsuccess = () => {
        if (!req.result) return resolve(null);
        const updated = { ...req.result, ...updates };
        store.put(updated);
        tx.oncomplete = () => resolve(updated);
      };
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn('Failed to update cached message in IndexedDB:', err);
  }
}

/**
 * Delete a single message from cache
 */
export async function deleteCachedMessage(messageId) {
  try {
    const db = await getDB();
    const tx = db.transaction('messages', 'readwrite');
    tx.objectStore('messages').delete(messageId);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to delete cached message:', err);
  }
}

/**
 * Offline Sync Queue operations
 */
export async function enqueueOfflineMessage(queueItem) {
  try {
    const db = await getDB();
    const tx = db.transaction('offline_queue', 'readwrite');
    tx.objectStore('offline_queue').put({
      id: queueItem.id || `offline-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      created_at: new Date().toISOString(),
      ...queueItem,
    });
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to enqueue offline message:', err);
  }
}

export async function getOfflineQueue() {
  try {
    const db = await getDB();
    const tx = db.transaction('offline_queue', 'readonly');
    const req = tx.objectStore('offline_queue').getAll();
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn('Failed to read offline queue:', err);
    return [];
  }
}

export async function removeOfflineQueueItem(id) {
  try {
    const db = await getDB();
    const tx = db.transaction('offline_queue', 'readwrite');
    tx.objectStore('offline_queue').delete(id);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to remove offline queue item:', err);
  }
}
