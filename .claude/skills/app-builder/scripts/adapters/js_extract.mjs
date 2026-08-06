/**
 * JavaScript extraction: file list on stdin, index records as JSONL on stdout.
 *
 * Parses with acorn -- the parser inside eslint, vite, webpack and rollup, so it
 * is present in essentially any real JavaScript project, including ones with no
 * TypeScript at all. That is the point of this adapter existing separately: a
 * plain Node or browser codebase must be readable without a TypeScript install.
 *
 * Deliberately a sibling of ts_extract.mjs rather than a shared library. The two
 * emit the same records, and selftest.py is what keeps that true; what differs
 * is real, and belongs apart:
 *
 *   here only   CommonJS (require / module.exports) and JSDoc types
 *   there only  interfaces, type aliases, annotations, generics, decorators
 */
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [, , acornPath, root, jsxPath] = process.argv;
const acorn = await import(pathToFileURL(acornPath).href);

let Parser = acorn.Parser;
if (jsxPath) {
  try {
    const jsx = (await import(pathToFileURL(jsxPath).href)).default;
    Parser = acorn.Parser.extend(jsx());
  } catch { /* .jsx files will fall back to a parse error, and be reported */ }
}

const input = JSON.parse(readFileSync(0, 'utf8'));
const { files, repo } = input;

const rel = (p) =>
  p.replace(/\\/g, '/').slice(root.replace(/\\/g, '/').length + 1);
const trunc = (s, n = 160) => {
  s = String(s ?? '').replace(/\s+/g, ' ').trim();
  return s.length <= n ? s : s.slice(0, n - 1) + '…';
};

const out = [];
const minified = [];

/* ------------------------------------------------------------------ JSDoc */

/**
 * `{Type}` out of a JSDoc block. Without annotations JavaScript has no modal
 * form for ATTRIBUTE DETAIL to report, and a codebase that documents its types
 * has told you them -- there is no reason to throw that away.
 */
function jsdocOf(node, comments) {
  let best = null;
  for (const c of comments) {
    if (c.type !== 'Block' || !c.value.startsWith('*')) continue;
    if (c.end <= node.start && (best === null || c.end > best.end)) best = c;
  }
  if (!best) return null;
  // Only immediately preceding: anything further up documents something else.
  return best;
}

function jsdocTypes(node, comments) {
  const block = jsdocOf(node, comments);
  if (!block) return { type: null, returns: null };
  const text = block.value;
  const type = text.match(/@type\s*\{([^}]+)\}/);
  const returns = text.match(/@returns?\s*\{([^}]+)\}/);
  return {
    type: type ? trunc(type[1], 60) : null,
    returns: returns ? trunc(returns[1], 60) : null,
  };
}

/* ------------------------------------------------------------------ calls */

/** `dayjs` from `dayjs(x).startOf(y)` -- down the receiver chain to its root. */
function callRoot(node) {
  for (;;) {
    switch (node?.type) {
      case 'Identifier': return node.name;
      case 'ThisExpression': return 'this';
      case 'CallExpression': node = node.callee; continue;
      case 'MemberExpression': node = node.object; continue;
      case 'NewExpression': node = node.callee; continue;
      case 'ChainExpression': node = node.expression; continue;
      case 'ParenthesizedExpression': node = node.expression; continue;
      default: return null;
    }
  }
}

function walk(node, visit) {
  if (!node || typeof node.type !== 'string') return;
  visit(node);
  for (const key of Object.keys(node)) {
    if (key === 'type' || key === 'start' || key === 'end') continue;
    const value = node[key];
    if (Array.isArray(value)) {
      for (const child of value) if (child && typeof child.type === 'string') walk(child, visit);
    } else if (value && typeof value.type === 'string') {
      walk(value, visit);
    }
  }
}

/** Method calls as `root.name`, and bare calls separately -- see ts_extract. */
// Each entry is `[name, line]`: the call's own line, not the enclosing
// function's, so a report points at the call site rather than at a long
// method with an invitation to go looking.
const has = (list, name, line) => list.some(([n, l]) => n === name && l === line);

function collectCalls(node) {
  const calls = [], invokes = [];
  walk(node, (n) => {
    if (n.type !== 'CallExpression') return;
    const callee = n.callee;
    const line = lineOf(n);
    if (callee?.type === 'MemberExpression' && !callee.computed) {
      const rootName = callRoot(callee.object);
      const prop = callee.property?.name;
      if (rootName && prop) {
        const entry = `${rootName}.${prop}`;
        if (!has(calls, entry, line)) calls.push([entry, line]);
      }
    } else if (callee?.type === 'Identifier') {
      if (!has(invokes, callee.name, line)) invokes.push([callee.name, line]);
    }
  });
  return { calls, invokes };
}

// acorn is asked for locations at parse time, so a line is read off the node
// rather than recomputed by slicing the file -- which was O(n) per lookup and
// would be O(n²) now that every call site wants one.
const lineOf = (node) => node?.loc?.start?.line ?? 1;
const endOf = (node) => node?.loc?.end?.line ?? lineOf(node);

function methodRecord(node, name, src, comments) {
  const { calls, invokes } = collectCalls(node.body ?? node);
  const doc = jsdocTypes(node, comments);
  return {
    name,
    decorators: [],
    // Destructured parameters are the norm in React -- `({ label, onClick })`
    // is the component's contract, and reducing it to '?' throws away the part
    // worth reading. Falls back to the source text, as the TypeScript adapter
    // does, so the two agree on what a parameter list looks like.
    params: (node.params ?? []).map((p) =>
      p.name ?? p.argument?.name ?? p.left?.name
      ?? trunc(src.slice(p.start, p.end), 60)),
    returns: doc.returns,
    line: lineOf(node),
    end: endOf(node),
    async: Boolean(node.async),
    calls,
    invokes,
  };
}

function attrRecord(node, src, comments) {
  const doc = jsdocTypes(node, comments);
  const init = node.value;
  const rec = {
    name: node.key?.name ?? node.key?.value ?? '?',
    ann: doc.type,
    call: null, args: [], kw: [],
  };
  if (init?.type === 'CallExpression') rec.call = callRoot(init.callee) ?? null;
  else if (init?.type === 'NewExpression') rec.call = callRoot(init.callee) ?? null;
  else if (init) rec.args = [trunc(src.slice(init.start, init.end), 60)];
  if (node.static) rec.kw.push('static');
  return rec;
}

/* ------------------------------------------------------------------ files */

for (const entry of files) {
  const { path: absolute, mtime, commit } = entry;
  let source;
  try { source = readFileSync(absolute, 'utf8'); } catch (e) {
    out.push({ k: 'unreadable', lang: 'javascript', repo, path: rel(absolute),
               error: String(e).slice(0, 200) });
    continue;
  }
  const relpath = rel(absolute);

  // Minified output parses perfectly and is not source. Published packages ship
  // bundles at their own root, where no directory rule catches them.
  const lines = source.split(/\r?\n/);
  const longest = lines.reduce((m, l) => (l.length > m ? l.length : m), 0);
  if (longest > 2000 || (lines.length < 5 && source.length > 20000)) {
    minified.push(relpath);
    continue;
  }

  const comments = [];
  const options = {
    ecmaVersion: 'latest', locations: true, onComment: comments,
    allowHashBang: true, allowReturnOutsideFunction: true,
  };

  // ESM first, then script. The two differ only where it matters -- `import` is
  // a syntax error in a script, and CommonJS is perfectly legal in either.
  let ast = null;
  for (const sourceType of ['module', 'script']) {
    try {
      comments.length = 0;
      ast = Parser.parse(source, { ...options, sourceType });
      break;
    } catch { /* try the other */ }
  }
  if (ast === null) {
    out.push({ k: 'unparsed', lang: 'javascript', repo, path: relpath,
               error: 'acorn could not parse this file in module or script mode' });
    continue;
  }

  const imports = [];
  const exports = [];

  // CommonJS is invisible to an ESM-only walk, and it is half the JavaScript
  // ever written: `require` anywhere, `module.exports` and `exports.x` at any
  // depth, because both are ordinary expressions rather than declarations.
  walk(ast, (n) => {
    if (n.type === 'CallExpression' && n.callee?.name === 'require'
        && n.arguments[0]?.type === 'Literal') {
      imports.push({ mod: String(n.arguments[0].value), name: null, as: null });
    }
    if (n.type === 'AssignmentExpression' && n.left?.type === 'MemberExpression') {
      const object = n.left.object?.name;
      const prop = n.left.property?.name;
      if (object === 'module' && prop === 'exports') {
        if (n.right?.type === 'ObjectExpression') {
          for (const p of n.right.properties) {
            const key = p.key?.name ?? p.key?.value;
            if (key) exports.push(String(key));
          }
        } else {
          exports.push('default');
        }
      } else if (object === 'exports' && prop) {
        exports.push(prop);
      }
    }
  });

  for (const st of ast.body) {
    if (st.type === 'ImportDeclaration') {
      const mod = String(st.source.value);
      if (!st.specifiers.length) imports.push({ mod, name: null, as: null });
      for (const s of st.specifiers) {
        if (s.type === 'ImportDefaultSpecifier') {
          imports.push({ mod, name: 'default', as: s.local.name });
        } else if (s.type === 'ImportNamespaceSpecifier') {
          imports.push({ mod, name: '*', as: s.local.name });
        } else {
          imports.push({ mod, name: s.imported?.name ?? s.local.name, as: s.local.name });
        }
      }
    } else if (st.type === 'ExportNamedDeclaration') {
      const mod = st.source ? String(st.source.value) : null;
      for (const s of st.specifiers ?? []) {
        exports.push(s.exported?.name ?? s.local?.name);
        if (mod) imports.push({ mod, name: s.local?.name ?? null, as: s.exported?.name ?? null });
      }
      const d = st.declaration;
      if (d?.id?.name) exports.push(d.id.name);
      for (const decl of d?.declarations ?? []) if (decl.id?.name) exports.push(decl.id.name);
    } else if (st.type === 'ExportAllDeclaration') {
      exports.push('*');
      imports.push({ mod: String(st.source.value), name: '*', as: null });
    } else if (st.type === 'ExportDefaultDeclaration') {
      exports.push('default');
    }
  }

  out.push({
    k: 'module', lang: 'javascript', repo, path: relpath,
    pkg: relpath.replace(/\.(m|c)?jsx?$/, '').replace(/\//g, '.'),
    dir: relpath.includes('/') ? relpath.slice(0, relpath.lastIndexOf('/')) : '',
    loc: lines.length,
    mtime, commit,
    main: /\bcreateRoot\(|^#!/m.test(source),
    exports: [...new Set(exports.filter(Boolean))],
    imports,
    doc: null,
  });

  const classRecord = (node, name) => {
    const attrs = [], methods = [], assigns = [], nested = [];
    for (const m of node.body?.body ?? []) {
      if (m.type === 'PropertyDefinition') {
        (m.static ? assigns : attrs).push(
          m.static
            ? { name: m.key?.name ?? '?', value: trunc(source.slice(m.start, m.end), 240) }
            : attrRecord(m, source, comments));
      } else if (m.type === 'MethodDefinition') {
        methods.push(methodRecord(m.value, m.key?.name ?? m.kind, source, comments));
      }
    }
    return {
      k: 'class', lang: 'javascript', repo, path: relpath, mtime, commit,
      name,
      kind: 'class',
      bases: node.superClass ? [source.slice(node.superClass.start, node.superClass.end)] : [],
      keywords: [], decorators: [],
      line: lineOf(node),
      end: endOf(node),
      attrs, assigns, methods, nested,
      doc: null,
    };
  };

  const asFunction = (node, name) => ({
    ...methodRecord(node, name, source, comments),
    k: 'func', lang: 'javascript', repo, path: relpath, mtime, commit,
  });

  for (let st of ast.body) {
    if (st.type === 'ExportNamedDeclaration' && st.declaration) st = st.declaration;
    else if (st.type === 'ExportDefaultDeclaration') {
      const d = st.declaration;
      if (d?.type === 'ClassDeclaration') { out.push(classRecord(d, d.id?.name ?? 'default')); continue; }
      if (d?.type === 'FunctionDeclaration' || d?.type === 'ArrowFunctionExpression'
          || d?.type === 'FunctionExpression') {
        out.push(asFunction(d, d.id?.name ?? 'default'));
      }
      continue;
    }

    if (st.type === 'ClassDeclaration') {
      out.push(classRecord(st, st.id?.name ?? 'default'));
    } else if (st.type === 'FunctionDeclaration') {
      out.push(asFunction(st, st.id?.name ?? 'default'));
    } else if (st.type === 'VariableDeclaration') {
      // `const Component = (props) => {...}` -- most modern code lives here
      for (const d of st.declarations) {
        const init = d.init;
        if (init?.type === 'ArrowFunctionExpression' || init?.type === 'FunctionExpression') {
          out.push(asFunction(init, d.id?.name ?? 'default'));
        } else if (init?.type === 'ClassExpression') {
          out.push(classRecord(init, d.id?.name ?? 'default'));
        }
      }
    }
  }
}

if (minified.length) {
  process.stderr.write(
    `  skipped ${minified.length} minified file(s), e.g. ${minified[0]}\n`);
}
process.stdout.write(out.map((r) => JSON.stringify(r)).join('\n') + '\n');
