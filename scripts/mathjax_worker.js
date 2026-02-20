#!/usr/bin/env node
// mathjax_worker.js — Batch LaTeX-to-speech via mathjax-full + SRE.
//
// Reads one LaTeX math string per line from stdin.
// Writes one JSON result per line to stdout: {"speech":"..."} or {"error":"..."}.
// Exits when stdin closes.

const { mathjax } = require('mathjax-full/js/mathjax.js');
const { TeX } = require('mathjax-full/js/input/tex.js');
const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
const { SerializedMmlVisitor } = require('mathjax-full/js/core/MmlTree/SerializedMmlVisitor.js');
const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');
const sre = require('speech-rule-engine');
const readline = require('readline');

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);

const packages = AllPackages.filter(p => p !== 'bussproofs');
const tex = new TeX({ packages });
const html = mathjax.document('', { InputJax: tex });
const visitor = new SerializedMmlVisitor();

sre.setupEngine({ domain: 'mathspeak', style: 'default', locale: 'en' });

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', (line) => {
  const latex = line.trim();
  if (!latex) {
    console.log(JSON.stringify({ error: 'empty input' }));
    return;
  }
  try {
    const node = html.convert(latex, { display: true });
    const mml = visitor.visitTree(node);
    const speech = sre.toSpeech(mml);
    console.log(JSON.stringify({ speech }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
  }
});
