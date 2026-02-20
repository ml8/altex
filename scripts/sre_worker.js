#!/usr/bin/env node
// sre_worker.js — Batch MathML-to-speech via Speech Rule Engine.
//
// Reads one MathML string per line from stdin.
// Writes one JSON result per line to stdout: {"speech":"..."} or {"error":"..."}.
// Exits when stdin closes.

const sre = require('speech-rule-engine');
const readline = require('readline');

sre.setupEngine({ domain: 'mathspeak', style: 'default', locale: 'en' });

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', (line) => {
  const mml = line.trim();
  if (!mml) {
    console.log(JSON.stringify({ error: 'empty input' }));
    return;
  }
  try {
    const speech = sre.toSpeech(mml);
    console.log(JSON.stringify({ speech }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
  }
});
