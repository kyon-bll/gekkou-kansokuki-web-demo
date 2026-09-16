#!/usr/bin/env node
'use strict';
// Optional development tests. The game itself does not require Node or any dependency.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const context = vm.createContext({console});
for (const id of ['game-data', 'game-core']) {
  const match = html.match(new RegExp(`<script id="${id}">([\\s\\S]*?)<\\/script>`));
  assert.ok(match, `${id} script is present`);
  vm.runInContext(match[1], context, {filename: id});
}
const {core, data} = vm.runInContext('({core:GameCore,data:GAME_DATA})', context);
const plain = value => JSON.parse(JSON.stringify(value));

test('all inline scripts parse', () => {
  let count = 0;
  for (const [, id, code] of html.matchAll(/<script id="([^"]+)">([\s\S]*?)<\/script>/g)) {
    new vm.Script(code, {filename: id});
    count++;
  }
  assert.equal(count, 3);
});
test('initial state contains four unique books and an intentionally misplaced book', () => {
  const s = core.initialState();
  assert.equal(core.validate(s), true);
  assert.equal(Object.keys(s.locations).length, 4);
  assert.equal(core.evaluate(s).solved, false);
  assert.equal(s.locations.eibon, 'shelf:1');
});
test('every book can be carried at once; no limited staging slots', () => {
  const s = core.initialState();
  data.books.forEach(b => assert.equal(core.pick(s, b.id).ok, true));
  assert.equal(core.at(s, 'hand').length, 4);
  assert.equal(s.selected, 'eibon');
  core.validate(s);
});
test('wrong shelving is allowed and does not auto-correct', () => {
  const s = core.initialState();
  core.pick(s, 'demon');
  assert.equal(core.move(s, 'demon', 'shelf:3').ok, true);
  assert.equal(s.locations.demon, 'shelf:3');
  assert.equal(s.selected, null);
  assert.equal(core.evaluate(s).solved, false);
});
test('occupied slots do not overwrite or lose either book', () => {
  const s = core.initialState();
  core.pick(s, 'demon');
  const before = JSON.stringify(s);
  assert.equal(core.move(s, 'demon', 'shelf:1').reason, 'occupied');
  assert.equal(JSON.stringify(s), before);
});
test('the same destination for the same book is harmless', () => {
  const s = core.initialState();
  assert.equal(core.move(s, 'eibon', 'shelf:1').ok, true);
  assert.equal(core.at(s, 'shelf:1').length, 1);
});
test('floor and side shelf accept all four books; all can be retrieved', () => {
  const s = core.initialState();
  for (const location of ['floor', 'side', 'desk']) {
    for (const b of data.books) assert.equal(core.move(s, b.id, location).ok, true);
    assert.equal(core.at(s, location).length, 4);
    for (const b of data.books) core.pick(s, b.id);
    assert.equal(core.at(s, 'hand').length, 4);
  }
});
test('invalid book, destination and out-of-range slots leave state unchanged', () => {
  const s = core.initialState();
  const before = JSON.stringify(s);
  for (const [id, destination] of [['unknown','floor'],['demon','shelf:4'],['arcana','void'],['demon','shelf:-1'],['eibon','__proto__']]) {
    assert.equal(core.move(s, id, destination).ok, false);
  }
  assert.equal(JSON.stringify(s), before);
});
test('correct order solves the shelf, not merely collecting or reading all books', () => {
  const s = core.initialState();
  data.books.forEach(b => {core.pick(s, b.id); core.markRead(s,b.id);});
  assert.equal(core.evaluate(s).solved, false);
  data.shelf.order.forEach((id,i) => assert.equal(core.move(s,id,`shelf:${i}`).ok,true));
  assert.equal(core.evaluate(s).solved, true);
  assert.equal(core.evaluate(s).filled, 4);
  // Solving the pure model does not unlock a story event itself.
  assert.equal(s.flags.solved, false);
  assert.equal(s.flags.finished, false);
});
test('all 24 full permutations are allowed, with exactly one solution', () => {
  function permutations(items) {return items.length ? items.flatMap((item,i) => permutations(items.filter((_,j)=>j!==i)).map(tail=>[item,...tail])) : [[]];}
  let solutions = 0;
  const orders = permutations(plain(data.shelf.order));
  assert.equal(orders.length,24);
  for (const order of orders) {
    const s = core.initialState();
    data.books.forEach(b=>core.pick(s,b.id));
    order.forEach((id,i)=>assert.equal(core.move(s,id,`shelf:${i}`).ok,true));
    if(core.evaluate(s).solved)solutions++;
    core.validate(s);
  }
  assert.equal(solutions,1);
});
test('reading twice does not duplicate notebook read flags', () => {
  const s=core.initialState();
  assert.equal(core.markRead(s,'demon'),true);
  assert.equal(core.markRead(s,'demon'),true);
  assert.equal(core.markRead(s,'not-a-book'),false);
  assert.deepEqual(plain(s.read),['demon']);
});
test('reset produces independent clean state', () => {
  const a=core.initialState();core.pick(a,'eibon');a.notes.push({id:'test'});a.flags.finished=true;
  const b=core.initialState();
  assert.equal(b.locations.eibon,'shelf:1');
  assert.equal(b.selected,null);
  assert.equal(b.notes.length,0);
  assert.equal(b.flags.finished,false);
});
test('10,000 deterministic moves preserve invariants and book count', () => {
  const s=core.initialState();const ids=data.books.map(b=>b.id);const places=['hand','floor','side','desk',...core.slots];let seed=48271;
  const rng=()=>{seed=(seed*16807)%2147483647;return seed;};
  for(let i=0;i<10000;i++) {
    const id=ids[rng()%ids.length],loc=places[rng()%places.length];
    if(i%3===0)core.pick(s,id);else core.move(s,id,loc);
    core.validate(s);
    assert.equal(Object.keys(s.locations).length,4);
  }
});
test('HTML contains no external runtime dependencies or network calls', () => {
  assert.doesNotMatch(html, /<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i);
  assert.doesNotMatch(html, /\b(?:fetch|XMLHttpRequest|WebSocket|importScripts)\s*\(/);
  assert.doesNotMatch(html, /@import\s|url\(\s*["']?https?:/);
});


test('the approved chart and data use the same four books and starting places', () => {
  assert.deepEqual(plain(data.shelf.order.map(id=>core.book(id).title)),['悪魔信仰','星辰の書','妖の秘術','エイボンの書']);
  assert.equal(data.shelf.title,'窓辺の棚');
  assert.equal(core.initialState().locations[data.rescueBook],'floor');
  assert.equal(core.initialState().locations.stars,'desk');
  assert.equal(core.initialState().locations.arcana,'desk');
});
test('moving the rescue book triggers rescue once and without permission or reading', () => {
  const s=core.initialState();
  assert.equal(s.flags.rescued,false);
  const first=core.pick(s,data.rescueBook);
  assert.equal(first.ok,true);
  assert.equal(first.rescued,true);
  assert.equal(s.flags.rescued,true);
  assert.equal(s.flags.chartFound,false);
  assert.equal(s.read.length,0);
  assert.equal(core.move(s,data.rescueBook,'floor').rescued,false);
  assert.equal(core.pick(s,data.rescueBook).rescued,false);
});
test('unsuccessful or same-place moves cannot trigger rescue', () => {
  const s=core.initialState();
  assert.equal(core.move(s,data.rescueBook,'shelf:1').ok,false);
  assert.equal(s.flags.rescued,false);
  assert.equal(core.move(s,data.rescueBook,'floor').rescued,false);
  assert.equal(s.flags.rescued,false);
});
test('all successful movement paths out of the first book position trigger rescue', () => {
  for(const loc of ['hand','desk','side','shelf:0']) {
    const s=core.initialState();
    const result=core.move(s,data.rescueBook,loc);
    assert.equal(result.rescued,true);
    assert.equal(s.flags.rescued,true);
    assert.equal(s.flags.chartFound,false);
  }
});
test('correct placement activates the shelf once, without chart or read flags', () => {
  const s=core.initialState();
  assert.equal(core.activateShelf(s),false);
  data.books.forEach(b=>core.pick(s,b.id));
  data.shelf.order.forEach((id,i)=>core.move(s,id,`shelf:${i}`));
  assert.equal(s.flags.chartFound,false);
  assert.equal(s.read.length,0);
  assert.equal(core.activateShelf(s),true);
  assert.equal(s.flags.solved,true);
  assert.equal(s.flags.diaryRead,false);
  assert.equal(s.flags.finished,false);
  assert.equal(core.activateShelf(s),false);
  core.pick(s,'eibon');
  assert.equal(s.flags.solved,true);
  core.move(s,'eibon','shelf:3');
  assert.equal(core.activateShelf(s),false);
});
test('discovered paper, unlocked reward and diary do not occupy book slots', () => {
  const s=core.initialState();
  s.flags.rescued=true;s.flags.chartFound=true;s.flags.solved=true;s.flags.diaryRead=true;
  for(const b of data.books)core.move(s,b.id,'floor');
  assert.equal(s.flags.chartFound,true);
  assert.equal(s.flags.solved,true);
  assert.equal(Object.keys(s.locations).length,4);
  assert.equal(core.book('diary'),undefined);
  assert.equal(core.book('chart'),undefined);
  assert.equal(core.validate(s),true);
});
test('reset clears rescue, chart, reward, diary and reference panel state', () => {
  const a=core.initialState();
  ['rescued','chartFound','solved','diaryRead','finished'].forEach(f=>a.flags[f]=true);
  a.chartOpen=true;
  const b=core.initialState();
  ['rescued','chartFound','solved','diaryRead','finished'].forEach(f=>assert.equal(b.flags[f],false));
  assert.equal(b.chartOpen,false);
});
test('original dialogue and time-order puzzle do not remain in the revised runtime', () => {
  for(const old of ['talkMan','flags.task','read-arrangement','丘の灯り','小さな渡し','銀の鍵','帰るところ','同じ夜の話'])assert.ok(!html.includes(old),old);
  assert.ok(!plain(data.story).completion.some(([speaker])=>speaker==='おじさん'));
  assert.equal(data.story.rescue[0][1],'助かったぜ');
  assert.ok(data.diary.page.startsWith('〇月✕日　弟が子どもを連れてきた。'));
});
