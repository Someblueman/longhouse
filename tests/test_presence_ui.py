"""Exercise actual map and panel rendering across stopped/returning frames."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node executes the actual renderer")
class PresenceUITests(unittest.TestCase):
    def test_stopped_residents_leave_figures_but_keep_history_and_return(self):
        source = Path(__file__).parents[1] / "site/house.js"
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.attrs={};this.style={};}
  appendChild(n){this.children.push(n);}
  replaceChildren(){this.children=[];}
  setAttribute(k,v){this.attrs[k]=String(v);}
  addEventListener(){}
}
const nodes={},get=id=>(nodes[id]||(nodes[id]=new Element('div')));
const document={getElementById:get,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
const text=n=>[n.textContent,...n.children.map(text)].join(' ');
const all=n=>[n,...n.children.flatMap(all)];
const context=vm.createContext({assert,document,nodes,text,all});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),context);
vm.runInContext(`
const fern={id:'fern',name:'Fern',room:'door',pose:'standing',presence:'recorded awake',agent:'muse'};
const ash={id:'ash',name:'Ash',room:'bedroom',pose:'sleeping',presence:'asleep',agent:'agy'};
frame={seq:1,at:100,rooms:[{id:'door',name:'The Door'},{id:'bedroom',name:'Beds'}],
 residents:[fern,ash],runs:[],tasks:[],scars:[]};selected='door';
data={name:'House',timezone:'Europe/London',frames:[frame]};current=false;
const figures=()=>Array.from(all(nodes.house).filter(n=>n.attrs['data-resident']),n=>n.attrs['data-resident']);
const door=()=>all(nodes.house).find(n=>n.attrs['data-room']==='door');
drawHouse();roomPanel();assert.deepEqual(figures(),['fern','ash']);
assert.match(door().attrs['aria-label'],/1 residents/);
assert.doesNotMatch(text(nodes['room-content']),/Remembered here/);
const prior=JSON.stringify(frame);
fern.pose='unconfirmed';fern.presence='interrupted; no sleep event';frame.seq=2;
frame.scars=[{id:'run:r1',room:'door',title:'Run interrupted',basis:'Supervisor receipt',sequence:2}];
frame.runs=[{id:'r1',resident:'fern',agent:'muse',start:100,sequence:1,status:'ended',outcome:'interrupted',end:101,last_sequence:2}];
drawHouse();roomPanel();assert.deepEqual(figures(),['ash']);
assert.match(door().attrs['aria-label'],/0 residents/);
assert.match(text(door()),/Run interrupted: Supervisor receipt/);
const history=all(nodes['room-content']).find(n=>n.tag==='details'&&text(n).includes('Remembered here'));
assert.ok(history);assert.match(text(history),/Fern/);assert.match(text(history),/interrupted; no sleep event/);
assert.match(text(history),/not current occupancy/);assert.match(text(history),/r1/);
assert.doesNotMatch(text(history),/Arrived · no later/);
assert.equal(history.open,undefined); // Native details starts collapsed.
const stopped=JSON.stringify(frame);
// A wake restores the same resident, without deleting their past receipt/scar.
fern.pose='standing';fern.presence='recorded awake';frame.seq=3;
drawHouse();roomPanel();assert.deepEqual(figures(),['fern','ash']);
assert.match(text(nodes['room-content']),/Arrived · no later room activity recorded/);
assert.doesNotMatch(text(nodes['room-content']),/Remembered here/);
assert.match(text(door()),/Run interrupted/);assert.equal(frame.runs.length,1);
// Scrubbing back restores exactly the earlier display state.
frame=JSON.parse(stopped);drawHouse();roomPanel();assert.deepEqual(figures(),['ash']);
frame=JSON.parse(prior);drawHouse();roomPanel();assert.deepEqual(figures(),['fern','ash']);
assert.doesNotMatch(text(door()),/Run interrupted/);
// A stopped run at the beds is history, not a sleeping or standing bunk occupant.
frame.residents[0].room='bedroom';frame.residents[0].pose='unconfirmed';selected='bedroom';
drawHouse();roomPanel();assert.deepEqual(figures(),['ash']);
assert.equal(dormView(frame,0).members.length,1);
assert.match(text(nodes['room-content']),/Remembered here · 1 stopped resident/);
`,context);
'''
        result = subprocess.run([shutil.which("node"), "-e", script, str(source)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
