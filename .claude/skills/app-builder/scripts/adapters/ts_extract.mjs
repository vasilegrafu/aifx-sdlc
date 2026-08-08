/**
 * TypeScript extraction: file list on stdin, index records as JSON on stdout.
 *
 * Uses the TypeScript compiler's own parser rather than a regex, and finds it
 * where the project already installed it -- if you are reading a TypeScript
 * codebase, TypeScript is present by definition.
 *
 * One process for the whole repository. Emits the same record shapes the Python
 * extractor emits, so nothing downstream has to know which produced them.
 */
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [, , tsModulePath, root] = process.argv;
const ts = (await import(pathToFileURL(tsModulePath).href)).default;

const input = JSON.parse(readFileSync(0, 'utf8'));
const files = input.files;
const repo = input.repo;

const rel = (p) => p.replace(/\\/g, '/').slice(root.replace(/\\/g, '/').length + 1);
/** This adapter is handed TypeScript only; JavaScript has its own. */
const langOf = () => 'typescript';

const trunc = (s, n = 160) => {
  s = String(s ?? '').replace(/\s+/g, ' ').trim();
  return s.length <= n ? s : s.slice(0, n - 1) + '…';
};
const text = (node, src) => {
  try { return trunc(node.getText(src)); } catch { return '?'; }
};

/** `StandardDbCtrl` from `StandardDbCtrl(x).select(y).filter(z)` */
function callRoot(node) {
  for (;;) {
    if (ts.isIdentifier(node)) return node.text;
    if (ts.isCallExpression(node)) { node = node.expression; continue; }
    if (ts.isPropertyAccessExpression(node)) { node = node.expression; continue; }
    if (ts.isNonNullExpression(node) || ts.isParenthesizedExpression(node)) {
      node = node.expression; continue;
    }
    return null;
  }
}

/**
 * `receiver.method(...)` and bare `fn(...)`, kept apart.
 * In React the bare ones carry most of the convention -- a component is defined
 * far more by which hooks it calls than by anything it declares.
 */
// Each entry is `[name, line]`. The line is the call's own, not the enclosing
// function's -- the difference between being pointed at a call site and being
// pointed at a forty-line method and told to look.
const has = (list, name, line) =>
  list.some(([n, l]) => n === name && l === line);

function collectCalls(node, src) {
  const calls = [], invokes = [];
  const lineOf = (n) =>
    src.getLineAndCharacterOfPosition(n.getStart(src)).line + 1;
  const walk = (n) => {
    if (ts.isCallExpression(n)) {
      const target = n.expression;
      if (ts.isPropertyAccessExpression(target)) {
        const rootName = callRoot(target.expression);
        if (rootName) {
          const entry = `${rootName}.${target.name.text}`;
          const line = lineOf(n);
          if (!has(calls, entry, line)) calls.push([entry, line]);
        }
      } else if (ts.isIdentifier(target)) {
        const line = lineOf(n);
        if (!has(invokes, target.text, line)) invokes.push([target.text, line]);
      }
    }
    ts.forEachChild(n, walk);
  };
  ts.forEachChild(node, walk);
  return { calls, invokes };
}

const modifierNames = (node) =>
  (ts.canHaveModifiers(node) ? ts.getModifiers(node) ?? [] : [])
    .filter((m) => !ts.isDecorator(m))
    .map((m) => ts.tokenToString(m.kind))
    .filter(Boolean);

const endLine = (node, src) =>
  src.getLineAndCharacterOfPosition(node.getEnd()).line + 1;

const decoratorNames = (node, src) =>
  (ts.canHaveDecorators(node) ? ts.getDecorators(node) ?? [] : [])
    .map((d) => text(d.expression, src));

function params(node) {
  return (node.parameters ?? []).map((p) => p.name.getText?.() ?? '?');
}

function methodRecord(node, src, name) {
  const { calls, invokes } = collectCalls(node, src);
  return {
    name,
    decorators: decoratorNames(node, src),
    params: params(node),
    returns: node.type ? text(node.type, src) : null,
    line: src.getLineAndCharacterOfPosition(node.getStart(src)).line + 1,
    end: endLine(node, src),
    async: modifierNames(node).includes('async'),
    calls,
    invokes,
  };
}

/** A property or field: the type is the payload, the initializer call is next. */
function attrRecord(node, src) {
  const rec = {
    name: node.name?.getText?.(src) ?? '?',
    ann: node.type ? text(node.type, src) : null,
    call: null, args: [], kw: [],
  };
  const init = node.initializer;
  if (init && ts.isCallExpression(init)) {
    rec.call = text(init.expression, src);
    rec.args = init.arguments.map((a) => trunc(text(a, src), 60));
  } else if (init) {
    rec.args = [trunc(text(init, src), 60)];
  }
  if (node.questionToken) rec.kw.push('optional');
  return rec;
}

function heritage(node, src) {
  const out = [];
  for (const clause of node.heritageClauses ?? []) {
    for (const t of clause.types) out.push(text(t, src));
  }
  return out;
}

/** class, interface, and a type alias whose right-hand side is an object type. */
function classRecord(node, src, mod, lang) {
  let members = node.members ?? [];
  if (ts.isTypeAliasDeclaration(node)) {
    members = ts.isTypeLiteralNode(node.type) ? node.type.members : [];
  }
  const attrs = [], methods = [], assigns = [], nested = [];
  for (const m of members) {
    if (ts.isPropertyDeclaration(m) || ts.isPropertySignature(m)) {
      if (modifierNames(m).includes('static')) {
        assigns.push({ name: m.name?.getText?.(src) ?? '?', value: text(m.initializer ?? m, src) });
      } else {
        attrs.push(attrRecord(m, src));
      }
    } else if (ts.isMethodDeclaration(m) || ts.isMethodSignature(m)) {
      methods.push(methodRecord(m, src, m.name?.getText?.(src) ?? '?'));
    } else if (ts.isConstructorDeclaration(m)) {
      methods.push(methodRecord(m, src, 'constructor'));
    } else if (ts.isGetAccessor(m) || ts.isSetAccessor(m)) {
      methods.push(methodRecord(m, src, m.name?.getText?.(src) ?? '?'));
    }
  }
  const kind = ts.isInterfaceDeclaration(node) ? 'interface'
    : ts.isTypeAliasDeclaration(node) ? 'type' : 'class';
  return {
    k: 'class', lang, repo, path: mod.path,
    mtime: mod.mtime, commit: mod.commit,
    name: node.name?.getText?.(src) ?? '?',
    kind,
    bases: heritage(node, src),
    keywords: modifierNames(node),
    decorators: decoratorNames(node, src),
    line: src.getLineAndCharacterOfPosition(node.getStart(src)).line + 1,
    end: endLine(node, src),
    attrs, assigns, methods, nested,
  };
}

const isExported = (node) => modifierNames(node).includes('export')
  || (node.modifiers ?? []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword);

const out = [];
const minified = [];
for (const entry of files) {
  const { path: absolute, mtime, commit } = entry;
  let source;
  try { source = readFileSync(absolute, 'utf8'); } catch (e) {
    out.push({ k: 'unreadable', lang: langOf(absolute), repo, path: rel(absolute),
               error: String(e).slice(0, 200) });
    continue;
  }
  const relpath = rel(absolute);
  const lang = langOf(absolute);

  // Minified output parses perfectly and is not source. A published package
  // ships bundles at its own root, where no directory rule can catch them, and
  // indexing one reports a "convention" that a tool wrote.
  const lines = source.split(/\r?\n/);
  const longest = lines.reduce((m, l) => (l.length > m ? l.length : m), 0);
  if (longest > 2000 || (lines.length < 5 && source.length > 20000)) {
    minified.push(relpath);
    continue;
  }
  const src = ts.createSourceFile(absolute, source, ts.ScriptTarget.Latest, true);

  const imports = [], exports = [];
  for (const st of src.statements) {
    if (ts.isImportDeclaration(st)) {
      const mod = st.moduleSpecifier.getText(src).replace(/['"]/g, '');
      const clause = st.importClause;
      if (!clause) { imports.push({ mod, name: null, as: null }); continue; }
      if (clause.name) imports.push({ mod, name: 'default', as: clause.name.text });
      const b = clause.namedBindings;
      if (b && ts.isNamedImports(b)) {
        for (const el of b.elements) {
          imports.push({ mod, name: (el.propertyName ?? el.name).text, as: el.name.text });
        }
      } else if (b && ts.isNamespaceImport(b)) {
        imports.push({ mod, name: '*', as: b.name.text });
      }
    } else if (ts.isExportDeclaration(st)) {
      // `export * from './x'` and `export { A } from './x'` -- the barrel
      const mod = st.moduleSpecifier?.getText(src).replace(/['"]/g, '') ?? null;
      if (st.exportClause && ts.isNamedExports(st.exportClause)) {
        for (const el of st.exportClause.elements) {
          exports.push(el.name.text);
          if (mod) imports.push({ mod, name: (el.propertyName ?? el.name).text, as: el.name.text });
        }
      } else if (mod) {
        exports.push('*');
        imports.push({ mod, name: '*', as: null });
      }
    } else if (isExported(st)) {
      if (st.name) exports.push(st.name.getText(src));
      if (ts.isVariableStatement(st)) {
        for (const d of st.declarationList.declarations) exports.push(d.name.getText(src));
      }
    }
  }

  const mod = {
    k: 'module', lang, repo, path: relpath,
    pkg: relpath.replace(/\.(tsx?|jsx?)$/, '').replace(/\//g, '.'),
    dir: relpath.includes('/') ? relpath.slice(0, relpath.lastIndexOf('/')) : '',
    loc: source.split('\n').length,
    mtime, commit,
    main: /\bcreateRoot\(|\brender\(|^#!/m.test(source),
    exports, imports,
  };
  out.push(mod);

  for (const st of src.statements) {
    if (ts.isClassDeclaration(st) || ts.isInterfaceDeclaration(st)
        || ts.isTypeAliasDeclaration(st)) {
      if (ts.isTypeAliasDeclaration(st) && !ts.isTypeLiteralNode(st.type)) continue;
      out.push(classRecord(st, src, mod, lang));
    } else if (ts.isFunctionDeclaration(st) && st.name) {
      out.push({ ...methodRecord(st, src, st.name.text),
                 k: 'func', lang, repo, path: relpath,
                 mtime, commit });
    } else if (ts.isExportAssignment(st) && !st.isExportEquals) {
      // `export default <fn>` -- a plugin, a middleware, a wrapped component.
      // No name, so nothing recorded it before; what it calls is the whole
      // convention, and that was invisible.
      let expr = st.expression;
      while (ts.isParenthesizedExpression(expr)) expr = expr.expression;
      if (ts.isArrowFunction(expr) || ts.isFunctionExpression(expr)) {
        out.push({ ...methodRecord(expr, src, expr.name?.text ?? 'default'),
                   k: 'func', lang, repo, path: relpath, mtime, commit });
      }
    } else if (ts.isFunctionDeclaration(st) && !st.name) {
      out.push({ ...methodRecord(st, src, 'default'),
                 k: 'func', lang, repo, path: relpath, mtime, commit });
    } else if (ts.isVariableStatement(st)) {
      // `const Component = (props) => {...}` -- most React components live here
      for (const d of st.declarationList.declarations) {
        const init = d.initializer;
        if (init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))) {
          out.push({ ...methodRecord(init, src, d.name.getText(src)),
                     k: 'func', lang, repo, path: relpath,
                     mtime, commit });
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
