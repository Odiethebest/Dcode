import type { ThemeRegistrationRaw } from 'shiki';

/**
 * Shiki theme keyed to the Dcode palette (cool paper + indigo) so inspector code
 * reads as of-a-piece with the rest of the identity. Hexes are literal (Shiki
 * can't resolve CSS vars) and mirror index.css :root.
 */
const dcodeTheme: ThemeRegistrationRaw = {
  name: 'dcode',
  type: 'light',
  colors: { 'editor.background': '#edecf1', 'editor.foreground': '#1b1826' },
  settings: [
    { scope: ['comment'], settings: { foreground: '#8b8799', fontStyle: 'italic' } },
    {
      scope: ['keyword', 'storage', 'storage.type', 'keyword.control', 'constant.language', 'variable.language'],
      settings: { foreground: '#3a2fa0' },
    },
    { scope: ['string', 'string.quoted', 'constant.other.symbol', 'meta.string'], settings: { foreground: '#1f7a46' } },
    { scope: ['constant.numeric'], settings: { foreground: '#3a2fa0' } },
    {
      scope: ['entity.name.function', 'support.function', 'meta.function-call.generic'],
      settings: { foreground: '#1b1826', fontStyle: 'bold' },
    },
    { scope: ['entity.name.class', 'entity.name.type', 'support.class'], settings: { foreground: '#1b1826', fontStyle: 'bold' } },
    { scope: ['variable', 'variable.parameter'], settings: { foreground: '#1b1826' } },
  ],
};

export interface Tok {
  content: string;
  color?: string;
  bold?: boolean;
  italic?: boolean;
}

interface ShikiToken {
  content: string;
  color?: string;
  fontStyle?: number;
}
interface Highlighter {
  codeToTokens: (code: string, opts: { lang: string; theme: string }) => { tokens: ShikiToken[][] };
}

let highlighterPromise: Promise<Highlighter> | null = null;

function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    // Lazy + lean: fine-grained core + JS regex engine (no wasm) + Python-only
    // grammar, pulled only on the first citation click. Avoids bundling Shiki's
    // full language/theme set into the app.
    highlighterPromise = (async () => {
      const [core, engine, python] = await Promise.all([
        import('shiki/core'),
        import('shiki/engine/javascript'),
        import('@shikijs/langs/python'),
      ]);
      return core.createHighlighterCore({
        themes: [dcodeTheme],
        langs: [python.default],
        engine: engine.createJavaScriptRegexEngine({ forgiving: true }),
      }) as unknown as Promise<Highlighter>;
    })();
  }
  return highlighterPromise;
}

const ITALIC = 1;
const BOLD = 2;

/**
 * Tokenize Python with the Dcode theme. Returns null on load/parse failure so
 * the caller falls back to plain text (line numbers + cited highlight still work).
 */
export async function highlightPython(code: string): Promise<Tok[][] | null> {
  try {
    const highlighter = await getHighlighter();
    const { tokens } = highlighter.codeToTokens(code, { lang: 'python', theme: 'dcode' });
    return tokens.map((line) =>
      line.map((token) => ({
        content: token.content,
        color: token.color,
        bold: ((token.fontStyle ?? 0) & BOLD) !== 0 || undefined,
        italic: ((token.fontStyle ?? 0) & ITALIC) !== 0 || undefined,
      }))
    );
  } catch {
    return null;
  }
}
