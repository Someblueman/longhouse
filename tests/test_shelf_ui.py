"""Execute the actual shelf renderer against a minimal DOM; no visual claim."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is needed for the actual renderer')
class ShelfUITests(unittest.TestCase):
    def test_real_states_safe_links_reasons_and_historical_reset(self):
        source = Path(__file__).parents[1] / 'site/house.js'
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
}
const root=new Element('section'), document={getElementById:()=>root,createElement:tag=>new Element(tag)};
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const all=node=>[node,...node.children.flatMap(all)];
const context=vm.createContext({assert,document,URL,root,text,all});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),context);
vm.runInContext(`
data={timezone:'Europe/London'};frame={};shelf();
assert.match(text(root),/not activated/);
frame={residents:[{id:'resident-fixture',name:'Juniper'}],shelf:{enabled:true,policy:null,ideas:[],projects:[]}};shelf();
assert.match(text(root),/awaits ratification/);assert.match(text(root),/No ideas/);
assert.doesNotMatch(text(root),/Room for one Explorer round|council can choose/);
assert(text(root).includes("0 / 2 active projects · 0 unselected ideas"));
frame.shelf.policy='work-selection';
frame.shelf.explorer={resident:'resident-fixture',agent:'opencode',until:100};
frame.shelf.ideas=[
 {id:'draft',title:'<img src=x onerror=alert(1)>',status:'shelved',sources:['https://example.org/', 'javascript:alert(1)', 'https://user:secret@example.org/']},
 {id:'winner',title:'Already selected',status:'project',sources:[]},
 {id:'lost',title:'Lost idea',status:'graveyard',losses:2,history:[{reasons:['Too large for the first milestone']}]}];
frame.shelf.projects=[{id:'done',title:'Completed map',status:'done',milestone:'Demo',deadline:100,extended:false}];
shelf();
assert.doesNotMatch(text(root),/Active projects/);assert.match(text(root),/Finished projects/);
assert.match(text(root),/Completed map/);assert.doesNotMatch(text(root),/Already selected/);
assert.match(text(root),/Too large for the first milestone/);
assert.match(text(root),/Explorer: Juniper · OpenCode/);assert.doesNotMatch(text(root),/resident-fixture/);
assert.match(text(root),/see the recorded round above/);assert.doesNotMatch(text(root),/Room for one Explorer round/);
assert.equal(all(root).filter(n=>n.tag==='img').length,0);
const links=all(root).filter(n=>n.tag==='a');assert.equal(links.length,1);
assert.equal(links[0].href,'https://example.org/');assert.equal(links[0].rel,'noopener noreferrer');
frame.shelf.projects.push({id:'live',title:'Current build',status:'active',deadline:200});shelf();
assert.match(text(root),/Active projects/);assert.match(text(root),/Current build/);
frame.shelf.explorer=null;
frame.shelf.ideas.push({id:'second',status:'shelved'},{id:'third',status:'shelved'});
shelf();assert.match(text(root),/Project slot available/);assert.match(text(root),/no Explorer round needed/);
frame.shelf.projects.push({id:'another',title:'Another build',status:'active'});
shelf();assert.match(text(root),/Both project slots occupied/);
assert.doesNotMatch(text(root),/Selection open|council decision needed|council can choose/);
frame.shelf.projects[2].status='done';shelf();assert.match(text(root),/Project slot available/);
frame={};shelf();assert.doesNotMatch(text(root),/Completed map|Current build|Lost idea/);
assert.match(text(root),/not activated/);
`,context);
'''
        result = subprocess.run([shutil.which('node'), '-e', script, str(source)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_study_room_renders_only_when_recorded_and_links_to_shelf(self):
        source = Path(__file__).parents[1] / 'site/house.js'
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
}
const nodes={};
const get=id=>(nodes[id]||(nodes[id]=new Element('div')));
const document={getElementById:get,createElement:tag=>new Element(tag)};
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const all=node=>[node,...node.children.flatMap(all)];
const context=vm.createContext({assert,document,URL,nodes,text,all});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),context);
vm.runInContext(`
data={timezone:'Europe/London'};
const door={id:'door',name:'Door',floor:0,status:'open'};
frame={rooms:[door],residents:[],scars:[],tasks:[],floors:[{level:0,name:'Ground floor'}],shelf:{enabled:true,policy:null,ideas:[{id:'i1',status:'shelved'}],projects:[]}};
assert.deepEqual(floorRooms(frame,0).map(r=>r.id),['door']);
const studyBuild={id:'study',name:'The Study',floor:0,status:'construction',purpose:'Shelf room'};
frame.rooms.push(studyBuild);
assert.deepEqual(floorRooms(frame,0).map(r=>r.id),['door','study']);
assert.equal(roomStatus(studyBuild),'construction');
studyBuild.status='open';
assert.equal(roomStatus(studyBuild),'open');
selected='study';
roomPanel();
const panel=nodes['room-content'];
assert.match(text(panel),/1 shelved idea/);
const links=all(panel).filter(n=>n.tag==='a');
assert.equal(links.length,1);
assert.equal(links[0].href,'#shelf-card');
frame={rooms:[door],residents:[],scars:[],tasks:[],floors:[{level:0,name:'Ground floor'}]};
if(!floorRooms(frame,0).some(r=>r.id===selected))selected=null;
assert.equal(selected,null);
`,context);
'''
        result = subprocess.run([shutil.which('node'), '-e', script, str(source)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
