import '@testing-library/jest-dom';

// Node 26 ships an experimental native `localStorage` that is disabled unless
// `--localstorage-file` is passed; under jsdom it shadows the DOM Storage and
// leaves `window.localStorage` unusable, so every test's beforeEach throws
// `Cannot read properties of undefined (reading 'clear')`. Install a
// deterministic in-memory Storage so the suite works on any Node version
// (CI runs Node 20; local dev may be newer).
function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  } as Storage;
}

const memoryStorage = createMemoryStorage();
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: memoryStorage });
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', { configurable: true, value: memoryStorage });
}
