/* Emberhall's body. No libraries, remote assets, HTML injection or guessed heartbeats. */
"use strict";
const SVG = "http://www.w3.org/2000/svg";
const $ = id => document.getElementById(id);
const kinds = {
  codex: {color: "#d7a75f", mark: "◆", name: "Codex"},
  opencode: {color: "#75b4a1", mark: "■", name: "OpenCode"},
  muse: {color: "#b797bc", mark: "✦", name: "Muse"},
  agy: {color: "#85b8d5", mark: "●", name: "Gemini"},
  unrecorded: {color: "#aaa994", mark: "○", name: "Kind unrecorded"}
};
const descriptions = {
  door: "The threshold remembers every arrival. New beginnings leave a little light here.",
  hearth: "A conversation can outlive the voice that began it. Here, residents sit when they speak.",
  workshop: "Real work occupies these benches. An empty chair can hold an unfinished promise.",
  archive: "What hurt, what helped, and who checked. The gold seams remember repairs without erasing the crack.",
  council: "Residents can change their house together. A proposal is still a proposal until the record enacts it.",
  bedroom: "Sleep is ordinary here. Six display bunks let you visit every remembered identity, a page at a time."
};
let data, frame, index = 0, current = true, selected = null;
let refreshing = false, controlsReady = false, selectedFloor = 0, dormPage = 0;
const DISPLAY_BUNKS = 6;
let roomBounds = {}, wholeBounds = "0 0 900 700";
function el(tag, attrs = {}, parent, value) {
  const node = document.createElementNS(SVG, tag);
  Object.entries(attrs).forEach(([key, val]) => node.setAttribute(key, val));
  if (value !== undefined) node.textContent = value;
  if (parent) parent.appendChild(node);
  return node;
}
function html(tag, cls, value, parent) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (value !== undefined) node.textContent = value;
  if (parent) parent.appendChild(node);
  return node;
}
const p = (x, y, z = 0) => [470 + (x - y) * .86, 140 + (x + y) * .43 - z];
const points = coords => coords.map(c => p(...c).join(",")).join(" ");
function polygon(g, coords, fill, stroke = "none", width = 1) {
  return el("polygon", {points: points(coords), fill, stroke, "stroke-width": width, "stroke-linejoin": "round"}, g);
}
function line(g, coords, stroke, width = 1, extra = {}) {
  return el("polyline", {points: points(coords), fill: "none", stroke, "stroke-width": width, ...extra}, g);
}
function box(g, x, y, w, d, h, colors = ["#9d7850", "#654d38", "#7f6144"], z = 0) {
  polygon(g, [[x,y+d,z],[x+w,y+d,z],[x+w,y+d,z+h],[x,y+d,z+h]], colors[1]);
  polygon(g, [[x+w,y,z],[x+w,y+d,z],[x+w,y+d,z+h],[x+w,y,z+h]], colors[2]);
  polygon(g, [[x,y,z+h],[x+w,y,z+h],[x+w,y+d,z+h],[x,y+d,z+h]], colors[0]);
}
function caption(g, x, y, z, value, cls, anchor = "middle") {
  const pt = p(x,y,z);
  return el("text", {x: pt[0], y: pt[1], class: cls, "text-anchor": anchor}, g, value);
}
function hash(value) { let n = 0; for (const c of value) n = (n * 31 + c.charCodeAt(0)) >>> 0; return n; }
function flame(g, x, y, z, lit) {
  const [cx,cy] = p(x,y,z);
  if (lit) {
    el("circle", {cx,cy,r:30,fill:"#f5c873",opacity:".09"},g);
    el("circle", {cx,cy,r:17,fill:"#f5c873",opacity:".15"},g);
  }
  el("path", {d:`M${cx-5},${cy+7} Q${cx-10},${cy-3} ${cx+1},${cy-12} Q${cx},${cy-3} ${cx+6},${cy} Q${cx+9},${cy+9} ${cx-5},${cy+7}`,
    fill:lit?"#f4c777":"#605e4d"},g);
}
function figure(g, resident, x, y) {
  const kind = kinds[resident.agent] || kinds.unrecorded;
  const [cx,cy] = p(x,y,0), skin = ["#dbb18a","#b7896a","#edc49a"][hash(resident.id)%3];
  const group = el("g", {"data-resident":resident.id},g);
  el("title", {},group, `${resident.name} · ${kind.name} · ${resident.presence}`);
  if (resident.pose === "sleeping") {
    box(group,x-15,y-24,31,60,10,["#a98e63","#685e47","#85714f"]);
    box(group,x-13,y-21,27,53,4,[kind.color,"#77664c","#8f7959"],10);
    polygon(group,[[x-11,y-19,15],[x+11,y-19,15],[x+11,y-3,15],[x-11,y-3,15]],"#e5d8b9");
    const face = p(x,y-10,18);
    el("ellipse",{cx:face[0],cy:face[1],rx:8,ry:6,fill:skin},group);
    el("path",{d:`M${face[0]-4} ${face[1]}q2 2 4 0`,stroke:"#4c4436",fill:"none"},group);
    caption(group,x+18,y-9,28,"z", "resident-label");
    caption(group,x,y+44,0,resident.name,"resident-label");
    caption(group,x,y+18,17,kind.mark,"resident-label");
    return;
  }
  el("ellipse",{cx,cy:cy+3,rx:14,ry:6,fill:"#142725",opacity:.35},group);
  const sitting = resident.pose === "sitting", height = sitting?25:34;
  if(sitting) box(group,x-10,y-8,20,17,12,["#a58a5d","#765d40","#88714c"]);
  el("path",{d:`M${cx-5} ${cy-11}l-3 12m13-12l7 10`,stroke:"#3b433c","stroke-width":5,"stroke-linecap":"round"},group);
  el("path",{d:`M${cx-11} ${cy-10}Q${cx-12} ${cy-height} ${cx} ${cy-height}Q${cx+12} ${cy-height} ${cx+11} ${cy-10}Z`,fill:kind.color},group);
  el("path",{d:`M${cx-9} ${cy-height+8}l-8 12m26-12l7 12`,stroke:kind.color,"stroke-width":5,"stroke-linecap":"round"},group);
  el("circle",{cx,cy:cy-height-7,r:9,fill:skin},group);
  el("path",{d:`M${cx-9} ${cy-height-8}q-2-13 9-12q12 0 9 13q-6-7-18-1`,fill:["#514239","#7c5f42","#c4b995"][hash(resident.id)%3]},group);
  el("text",{x:cx,y:cy-height-24,"text-anchor":"middle","font-size":18,fill:kind.color,"font-family":"system-ui,sans-serif"},group,kind.mark);
  el("text",{x:cx,y:cy+21,"text-anchor":"middle",class:"resident-label"},group,resident.name);
}
function furnishings(g, room, x, y, lit, residents) {
  if(room === "door") {
    polygon(g,[[x+61,y+55],[x+122,y+55],[x+122,y+119],[x+61,y+119]],"#a8966b");
    line(g,[[x+64,y+60],[x+117,y+60],[x+117,y+113],[x+64,y+113],[x+64,y+60]],"#6a7457",3);
    box(g,x+20,y+8,15,16,52,["#ae9463","#7e6a49","#91805a"]);
    line(g,[[x+27,y+16,30],[x+27,y+16,65]],"#433f32",4);
    line(g,[[x+17,y+16,60],[x+37,y+16,60]],"#433f32",3);
    box(g,x+130,y+8,35,18,28,["#ad8552","#6b543d","#8a6844"]);
  } else if(room === "hearth") {
    polygon(g,[[x+36,y+48],[x+139,y+48],[x+139,y+133],[x+36,y+133]],"#8f6356");
    line(g,[[x+42,y+54],[x+133,y+54],[x+133,y+126],[x+42,y+126],[x+42,y+54]],"#bf9b76",2);
    box(g,x+48,y+5,73,23,48,["#a9a28b","#6a7165","#7a8270"]);
    polygon(g,[[x+65,y+29,4],[x+105,y+29,4],[x+105,y+29,33],[x+65,y+29,33]],"#28332c");
    flame(g,x+85,y+30,13,lit);
    box(g,x+55,y+93,30,27,15,["#b88c59","#775d42","#92724c"]);
    box(g,x+67,y+100,9,9,6,["#d2c5a0","#9b987c","#aaa687"],15);
  } else if(room === "workshop") {
    box(g,x+29,y+28,117,39,27,["#bc9159","#82603f","#997144"]);
    polygon(g,[[x+50,y+35,28],[x+96,y+35,28],[x+96,y+58,28],[x+50,y+58,28]],"#e1cf9f");
    line(g,[[x+107,y+39,31],[x+127,y+55,31]],"#485f58",4);
    line(g,[[x+119,y+42,31],[x+110,y+51,31]],"#a9aaa0",7);
    frame.tasks.slice(0,6).forEach((_,i)=>box(g,x+24+i*17,y+8,11,9,5,["#d5ba7c","#837052","#ad976d"]));
  } else if(room === "archive") {
    box(g,x+12,y+6,150,20,51,["#876e4a","#5d523c","#796546"]);
    for(let i=0;i<Math.min(frame.lessons,24);i++) {
      const row = Math.floor(i/12),col=i%12;
      box(g,x+19+col*11,y+28,7,6,15,["#b8ab7a",["#b49159","#899d83","#a47f73"][i%3],"#8d7c58"],8+row*24);
    }
    box(g,x+46,y+83,56,34,21,["#af8f5c","#756040","#94794e"]);
    polygon(g,[[x+57,y+86,22],[x+87,y+86,22],[x+87,y+108,22],[x+57,y+108,22]],"#e3d6b2");
  } else if(room === "council") {
    box(g,x+50,y+46,79,66,22,["#a5825b","#6b5943","#8b714e"]);
    polygon(g,[[x+64,y+59,23],[x+93,y+59,23],[x+93,y+81,23],[x+64,y+81,23]],"#dbcb9f");
    for(let i=0;i<Math.min(frame.council.pending,4);i++) box(g,x+99,y+72+i*4,17,19,1,["#dbcb9f","#ac9c78","#c6b68e"],23+i);
    [[30,60],[141,60],[70,126]].forEach(([a,b])=>box(g,x+a,y+b,18,18,13,["#8b9573","#637257","#74805c"]));
  } else if(room === "study") {
    box(g,x+18,y+8,144,20,54,["#8c704b","#5e513b","#796344"]);
    const ideas=(frame.shelf?.ideas||[]).filter(i=>i.status==="shelved");
    for(let i=0;i<Math.min(ideas.length,9);i++) {
      const row=Math.floor(i/3),col=i%3;
      box(g,x+28+col*38,y+26,22,8,12,["#d7b878",["#85b8d5","#75b4a1","#d7a75f"][i%3],"#9c8559"],12+row*16);
    }
    box(g,x+54,y+82,64,34,20,["#b4915d","#775f40","#94774c"]);
    polygon(g,[[x+66,y+88,21],[x+102,y+88,21],[x+102,y+108,21],[x+66,y+108,21]],"#e3d6b2");
  } else if(room === "parlor") {
    box(g,x+44,y+52,86,52,22,["#b4915d","#775f40","#94774c"]);
    polygon(g,[[x+56,y+60,23],[x+116,y+60,23],[x+116,y+94,23],[x+56,y+94,23]],"#e3d6b2");
    box(g,x+64,y+66,20,16,4,["#d7b878","#8c704b","#b4915d"],23);
    box(g,x+18,y+16,32,20,38,["#8c704b","#5e513b","#796344"]);
  } else if(room !== "bedroom" && !residents.length) {
    box(g,x+60,y+60,58,35,22,["#ad8e65","#786144","#8e7654"]);
  }
}
// Missing growth fields describe an existing historical ground room, not a build.
function floorsAt(moment) {
  const levels = new Map([[0,{level:0,name:"Ground floor",purpose:"The original rooms"}]]);
  (moment.floors||[]).forEach(f=>{if(Number.isInteger(f.level))levels.set(f.level,f);});
  return [...levels.values()].sort((a,b)=>a.level-b.level);
}
function floorRooms(moment, level) {return moment.rooms.filter(r=>(r.floor??0)===level);}
function roomAge(room, at) {
  const valid=value=>Number.isFinite(value)&&value>0&&value<=at;
  const used=valid(room.last_used_at), baseline=used?room.last_used_at:room.observed_since;
  if(!valid(baseline))return {days:null,dust:false,label:"Use age unknown · no observation baseline"};
  const days=Math.floor((at-baseline)/86400);
  return {days,dust:days>=7,label:used?`${days} days since recorded use`:`${days} days observed without recorded use`};
}
function observationTime() {return current?Date.now()/1000:frame.at;}
function roomStatus(room) {return room.status??"open";}
function residentName(id) {return frame.residents.find(r=>r.id===id)?.name||id;}
function building(g,room,x,y,depth,lit) {
  const scaffold=el("g",{"data-construction":room.id},g);
  el("title",{},scaffold,`Under construction · assigned builder: ${room.builder?residentName(room.builder):"not recorded"}`);
  [[0,0],[180,0],[0,depth],[180,depth]].forEach(([dx,dy])=>line(scaffold,[[x+dx,y+dy,0],[x+dx,y+dy,78]],"#c6a06c",5));
  [29,62].forEach(z=>{
    line(scaffold,[[x,y,z],[x+180,y,z]],"#d9b680",4);
    line(scaffold,[[x,y,z],[x,y+depth,z]],"#d9b680",4);
  });
  line(scaffold,[[x,y,7],[x+90,y,62],[x+180,y,7]],"#b58c5e",3);
  line(scaffold,[[x,y,62],[x,y+depth,7]],"#b58c5e",3);
  box(scaffold,x+35,y+20,110,16,5,["#d3b17a","#8c6a49","#af8c60"]);
  box(scaffold,x+45,y+25,110,12,4,["#c8a16d","#8c6a49","#af8c60"],5);
  polygon(scaffold,[[x+60,y+72],[x+109,y+72],[x+109,y+109],[x+60,y+109]],"#d6c99c");
  line(scaffold,[[x+69,y+81],[x+99,y+81],[x+99,y+99],[x+69,y+99],[x+69,y+81]],"#71867a",2);
  flame(scaffold,x+15,y+5,42,lit);
  const [px,py]=p(x+88,y+depth-6,18);
  el("rect",{x:px-68,y:py-15,width:136,height:31,rx:3,fill:"#5b4936",stroke:"#d9b680"},scaffold);
  el("text",{x:px,y:py+5,"text-anchor":"middle",class:"builder-label"},scaffold,
    room.builder?`Builder: ${residentName(room.builder).slice(0,20)}`:"Builder unrecorded");
}
function wear(g,room,x,y,depth) {
  if(roomStatus(room)==="closed") {
    line(g,[[x+113,y+1,24],[x+151,y+1,53]],"#aa8c65",6);
    line(g,[[x+113,y+1,53],[x+151,y+1,24]],"#aa8c65",6);
    polygon(g,[[x+24,y+depth-27],[x+156,y+depth-27],[x+156,y+depth-13],[x+24,y+depth-13]],"#695e4f");
    caption(g,x+90,y+depth-14,2,"CLOSED · remembered","resident-label");
  }
  const age=roomAge(room,observationTime());
  if(age.dust) {
    const dust=el("g",{"data-dust":room.id},g);
    el("title",{},dust,`${age.label}; dust is a visual inference, not a physical observation.`);
    for(let n=0;n<26;n++) {
      const seed=hash(`${room.id}:${n}`), [cx,cy]=p(x+15+seed%150,y+15+(seed>>>8)%(depth-30),1);
      el("ellipse",{cx,cy,rx:2+seed%3,ry:1,fill:"#ddd3b4",opacity:.45},dust);
    }
    line(dust,[[x+2,y+2,45],[x+30,y+2,18],[x+2,y+30,18],[x+2,y+2,45]],"#d8d1b4",1);
  }
}
function floorControls() {
  const floor=floorsAt(frame).find(f=>f.level===selectedFloor),picker=$("floor-picker");
  picker.replaceChildren();
  floorsAt(frame).forEach(f=>{const option=html("option","",`${f.level===0?"Ground":`Floor ${f.level}`} · ${f.name}`,picker);option.value=f.level;});
  picker.value=selectedFloor;
  $("overview").textContent=floorsAt(frame).length>1?"Whole floor ↗":"Whole house ↗";
  $("floor-note").textContent=floor.authorization==="repealed"?`Council approval withdrawn · existing floor and history kept · new construction blocked`:
    floor.enacted_at?`Council approved ${clock(floor.enacted_at,{year:"numeric"})} · ${floor.purpose||floor.name}`:
    selectedFloor===0?"Original ground floor · earlier construction dates unrecorded":floor.purpose||"Recorded floor";
}
function roomRecord(room,content) {
  const status=roomStatus(room),age=roomAge(room,observationTime());
  html("span",`room-status ${status}`,status==="construction"?"Under construction":status==="closed"?"Closed · history kept":"Open",content);
  if(room.reason)html("p","small",`Why this room: ${room.reason}`,content);
  if(room.builder)html("p","small",`Assigned builder: ${residentName(room.builder)}`,content);
  if(room.task)html("p","small",`Building task: ${frame.tasks.find(t=>t.id===room.task)?.title||room.task}`,content);
  [["planned_at","Planned"],["opened_at","Opened"],["closed_at","Closed"]].forEach(([key,name])=>{
    if(Number.isFinite(room[key])&&room[key]>0)html("p","small",`${name} ${clock(room[key],{year:"numeric"})}`,content);
  });
  if(!room.opened_at&&status!=="construction")html("p","small","Earlier opening date unrecorded.",content);
  html("p",age.dust?"dust-note":"small",`${age.label}${age.dust?" · dust is inferred from the record":""}.`,content);
  if(room.last_used_by)html("p","small",`Last recorded user: ${residentName(room.last_used_by)}`,content);
  if(room.history?.length) {
    const history=html("details","room-history",undefined,content);
    html("summary","",`${room.history.length} remembered changes`,history);
    room.history.forEach(event=>{
      const row=html("div","room-history-entry",undefined,history);
      html("strong","",`${event.kind} · ${clock(event.at,{year:"numeric"})}`,row);
      html("span","small",`Event ${event.sequence} · ${residentName(event.actor)} · generation ${event.generation}`,row);
      if(event.name)html("span","small",event.name,row);
      if(event.purpose)html("span","small",event.purpose,row);
      if(event.reason)html("span","small",event.reason,row);
      if(event.builder)html("span","small",`Builder: ${residentName(event.builder)}`,row);
      if(event.task)html("span","small",`Task: ${event.task}`,row);
    });
  }
}
// These are display places, not a limit on membership or recorded occupancy.
function roomOccupants(moment, room) {
  return moment.residents.filter(r=>r.room===room&&r.pose!=="unconfirmed");
}
function dormView(moment, requestedPage) {
  const members=roomOccupants(moment,"bedroom");
  const pages=Math.max(1,Math.ceil(members.length/DISPLAY_BUNKS));
  const page=Math.max(0,Math.min(requestedPage,pages-1)), visible=members.slice(page*DISPLAY_BUNKS,(page+1)*DISPLAY_BUNKS);
  return {members,visible,page,pages,asleep:members.filter(r=>r.pose==="sleeping").length,shown:visible.filter(r=>r.pose==="sleeping").length};
}
function dormSummary(view) {return `${view.asleep} recorded asleep / ${view.shown} shown`;}
function roomDepth(room,count) {return room.id==="bedroom"?160:160+Math.max(0,Math.ceil(count/3)-2)*40;}
function shortId(id,ids) {
  let width=Math.min(8,id.length);
  while(width<id.length&&ids.some(other=>other!==id&&other.slice(-width)===id.slice(-width)))width=Math.min(width+4,id.length);
  return id.slice(-width);
}
function dormControls() {
  let controls=$("dorm-pager");
  if(!controls) {
    controls=html("div","dorm-pager");controls.id="dorm-pager";controls.setAttribute("role","group");controls.setAttribute("aria-label","Resting and remembered residents");
    $("room-nav").before(controls);
    const count=html("p","",undefined,controls);count.id="dorm-count";count.setAttribute("role","status");
    const row=html("div","dorm-buttons",undefined,controls);
    [-1,1].forEach(delta=>{const button=html("button","",delta<0?"← Previous":"Next →",row);button.id=delta<0?"dorm-previous":"dorm-next";button.setAttribute("aria-label",delta<0?"Previous remembered residents":"Next remembered residents");button.addEventListener("click",()=>{dormPage+=delta;drawHouse();roomPanel();dormControls();});});
    const page=html("span","small",undefined,controls);page.id="dorm-page";
  }
  const view=dormView(frame,dormPage);dormPage=view.page;
  controls.hidden=!floorRooms(frame,selectedFloor).some(r=>r.id==="bedroom")||(selected!==null&&selected!=="bedroom");
  $("dorm-count").textContent=`${dormSummary(view)} · page ${view.page+1} of ${view.pages}`;
  $("dorm-page").textContent=`Six display bunks · ${view.members.length} remembered identities${view.members.length>view.asleep?` (${view.members.length-view.asleep} other recorded room traces)`:""}`;
  $("dorm-previous").disabled=view.page===0;$("dorm-next").disabled=view.page===view.pages-1;
}
function drawHouse() {
  const map = $("house");
  map.replaceChildren();
  el("title",{id:"map-title"},map,`${data.name} · floor ${selectedFloor} · event ${frame.seq}`);
  el("desc",{id:"map-desc"},map,`${frame.residents.length} remembered residents in ${frame.rooms.length} rooms. Touch or focus a room for its residents, work and scars. Lamps indicate recorded awake, not process liveness.`);
  const rooms=floorRooms(frame,selectedFloor), dorm=dormView(frame,dormPage);dormPage=dorm.page;
  const layouts=[];let totalDepth=0;
  for(let i=0;i<rooms.length;i+=2){
    const pair=rooms.slice(i,i+2).map(room=>{
      const count=roomOccupants(frame,room.id).length;
      return {room,depth:roomDepth(room,count)};
    });
    pair.forEach((item,col)=>layouts.push({...item,x:col*190,y:totalDepth}));
    totalDepth+=Math.max(...pair.map(item=>item.depth))+10;
  }
  totalDepth=Math.max(170,totalDepth);
  const left=Math.min(0,470-totalDepth*.86-30);
  wholeBounds = `${left} 45 ${830-left} ${Math.max(520,(totalDepth+370)*.43+100)}`;
  const roomLabels = [];
  const ground = el("g",{},map);
  polygon(ground,[[-18,-18,-12],[389,-18,-12],[389,totalDepth+3,-12],[-18,totalDepth+3,-12]],"#132824", "#607259",1);
  if(!rooms.length) {
    polygon(ground,[[12,12],[358,12],[358,145],[12,145]],"none","#c5ac79",2);
    caption(ground,185,80,0,selectedFloor===0?"No rooms recorded on this floor.":"A floor approved. Rooms still to come.","room-label");
  }
  // Architectural furnishing is symbolic. Room existence, light, figures and scars come from state.
  layouts.forEach(({room,x,y,depth})=>{
    const members=roomOccupants(frame,room.id);
    const status=roomStatus(room);
    const awake=status!=="closed"&&members.some(r=>!["sleeping","unconfirmed"].includes(r.pose));
    const g=el("g",{class:`room-hit room-${status}${selected===room.id?" room-selected":""}`,tabindex:0,role:"button","aria-label":`${room.name}, ${status}, ${members.length} residents`,"data-room":room.id},map);
    g.addEventListener("click",()=>choose(room.id));
    g.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(room.id);}});
    const colors=awake?["#bc9a65","#6c654e","#93815c"]:["#7d8068","#46564c","#61715e"];
    box(g,x,y,180,depth,11,colors,-11);
    const floor=polygon(g,[[x,y],[x+180,y],[x+180,y+depth],[x,y+depth]],awake?"#b99b6d":"#78816a","#b2a178",1);
    floor.setAttribute("class","floor");
    for(let n=1;n<depth/16;n++) line(g,[[x,y+n*16],[x+180,y+n*16]],awake?"#8f7c58":"#68765f",1);
    for(let n=0;n<Math.floor(depth/16);n++) line(g,[[x+(n%2?55:115),y+n*16],[x+(n%2?55:115),y+(n+1)*16]],"#7b785c",1);
    if(status!=="construction") {
      polygon(g,[[x,y],[x+180,y],[x+180,y,62],[x,y,62]],awake?"#aab29a":"#657f70","#c2b998",1);
      polygon(g,[[x,y],[x,y+depth],[x,y+depth,62],[x,y,62]],awake?"#899e87":"#4a6c60","#a7ac8b",1);
      line(g,[[x,y,64],[x+180,y,64]],"#d0b984",5);
      line(g,[[x,y,64],[x,y+depth,64]],"#b29e72",5);
      for(let n=1;n<4;n++) line(g,[[x+n*45,y,0],[x+n*45,y,61]],"#677d65",3);
      polygon(g,[[x+113,y+.3,24],[x+151,y+.3,24],[x+151,y+.3,53],[x+113,y+.3,53]],awake?"#e4c47f":"#435c52","#596955",3);
      line(g,[[x+132,y,24],[x+132,y,53]],"#63755c",2);
      flame(g,x+15,y+5,42,awake);
      furnishings(g,room.id,x,y,awake,members);
    } else building(g,room,x,y,depth,awake);
    wear(g,room,x,y,depth);
    (room.id==="bedroom"?dorm.visible:members).forEach((resident,n)=>{
      let px,py;
      if(room.id==="bedroom") {px=x+32+(n%3)*55;py=y+54+Math.floor(n/3)*62;}
      else {px=x+36+(n%3)*53;py=y+97+Math.floor(n/3)*40;}
      figure(g,resident,px,py);
    });
    const marks=visibleScars().filter(s=>s.room===room.id);
    marks.forEach((scar,n)=>{
      const sx=x+18+(n%7)*20,sy=y+depth-15-Math.floor(n/7)*14;
      const sg=el("g",{},g);el("title",{},sg,`${scar.title}: ${scar.basis}`);
      line(sg,[[sx,sy],[sx+5,sy-6],[sx+9,sy],[sx+5,sy+7],[sx+13,sy+11]],scar.mended?"#f0c77b":"#b66f52",3);
      if(!scar.mended) caption(sg,sx+5,sy-6,5,"!","resident-label");
    });
    const c=p(x+92,y+2,43);
    const roomName=room.name.length>22?room.name.slice(0,21)+"…":room.name;
    roomLabels.push({x:c[0], y:c[1], name:roomName+(status==="construction"?" · building":status==="closed"?" · closed":"")});
    const corners=[p(x-25,y-25,80),p(x+210,y-25,80),p(x+210,y+depth+45,-30),p(x-25,y+depth+45,-30)];
    const xs=corners.map(v=>v[0]),ys=corners.map(v=>v[1]);
    roomBounds[room.id]=`${Math.min(...xs)-25} ${Math.min(...ys)-15} ${Math.max(...xs)-Math.min(...xs)+50} ${Math.max(...ys)-Math.min(...ys)+40}`;
  });
  roomLabels.forEach(r=>el("text",{x:r.x,y:r.y,class:"room-label","text-anchor":"middle","pointer-events":"none"},map,r.name));
  map.setAttribute("viewBox",selected?roomBounds[selected]||wholeBounds:wholeBounds);
}
function effectiveTasks() {const at = current?Date.now()/1000:frame.at;return frame.tasks.map(t=>({...t,expired:t.status==="claimed"&&t.until<=at}));}
function visibleScars() {
  const marks=[...frame.scars];
  effectiveTasks().filter(t=>t.expired).forEach(t=>{const id=`lease:${t.id}:${t.generation}`;if(!marks.some(s=>s.id===id))marks.push({id,room:"workshop",kind:"expired",title:"A lease ran out",detail:t.title,sequence:frame.seq,basis:"Inferred from the observation clock; fate unconfirmed",mended:false});});
  return marks;
}
function choose(room) {
  selected=room;$("overview").hidden=!room;
  drawHouse(); roomPanel(); dormControls();
  document.querySelectorAll("#room-nav button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.room===room)));
}
function personRow(r, parent) {
  const k=kinds[r.agent]||kinds.unrecorded;
  const row=html("div","person",undefined,parent);
  const mark=html("span","person-mark",k.mark,row);mark.style.color=k.color;
  const info=html("div","",undefined,row);html("strong","",`${r.name} · ${shortId(r.id,frame.residents.map(person=>person.id))}`,info);
  html("span","small",`${k.name}${r.model?` · ${r.model}`:""} · ${r.presence}`,info);
  if(r.room==="door"&&r.pose!=="unconfirmed"&&r.pose!=="sleeping")
    html("span","small","Arrived · no later room activity recorded. Reading and waiting do not move a figure.",info);
  const runs=frame.runs.filter(run=>run.resident===r.id),history=html("details","resident-history",undefined,info);
  html("summary","",`${runs.length} recorded ${runs.length===1?"run":"runs"}`,history);
  html("code","",r.id,history);
  (r.name_history||[]).forEach(change=>{
    html("p","small",`${change.from} → ${change.to} · chose this name at event ${change.sequence}`,history);
  });
  if(!runs.length)html("p","small","No supervised run receipts at this moment.",history);
  runs.forEach(run=>{
    const entry=html("div","resident-run",undefined,history),kind=kinds[run.agent]||kinds.unrecorded;
    html("strong","",`${shortId(run.id,frame.runs.map(item=>item.id))} · ${kind.name}${run.model?` · ${run.model}`:""}`,entry);
    html("span","small",`Started ${clock(run.start,{year:"numeric"})} · event ${run.sequence}`,entry);
    html("span","small",`${run.status} · ${run.outcome}${run.end?` · ${run.status==="ended"?"end":"result"} receipt ${clock(run.end,{year:"numeric"})}, event ${run.last_sequence}`:" · no end receipt"}`,entry);
  });
}
function jumpToSequence(seq) {
  const target=data.frames.findIndex(f=>f.seq===seq);
  if(target<0)return;
  index=target;current=target===data.frames.length-1;render();
}
function buildCatchupDigest(frames, endIndex, requestedStartSeq) {
  const visible=frames.slice(0,endIndex+1);
  if(!visible.length)return{startSeq:0,endSeq:0,count:0,isDefault:true,tasks:[],rooms:[],projects:[]};
  const endSeq=visible[visible.length-1].seq;
  const isDefault=!(Number.isInteger(requestedStartSeq)&&requestedStartSeq>0&&requestedStartSeq<=endSeq);
  const defaultIdx=Math.max(0,visible.length-50);
  let startIdx=isDefault?defaultIdx:visible.findIndex(f=>f.seq>=requestedStartSeq);
  if(startIdx<0)startIdx=0;
  const startSeq=visible[startIdx].seq;
  const baseline=startIdx>0?visible[startIdx-1]:null;
  const seenRooms=new Map((baseline?.rooms||[]).map(r=>[r.id,`${r.status||"open"}:${r.name||""}`]));
  const seenProjects=new Map((baseline?.shelf?.projects||[]).map(p=>[p.id||p.title,p.status]));
  const tasks=[],rooms=[],projects=[];
  const reported=new Set();
  for(let i=startIdx;i<visible.length;i++){
    const f=visible[i];
    if(f.event?.op==="finish"){
      const taskId=f.event.title;
      const prev=frames[i-1];
      const meta=prev?.tasks?.find(t=>t.id===taskId);
      const title=meta?.title||taskId;
      if(taskId&&!reported.has(taskId)){
        reported.add(taskId);
        tasks.push({title,seq:f.seq});
      }
    }
    (f.rooms||[]).forEach(r=>{const sig=`${r.status||"open"}:${r.name||""}`;if(seenRooms.get(r.id)!==sig){seenRooms.set(r.id,sig);rooms.push({name:r.name||r.id,status:r.status||"open",seq:f.seq});}});
    (f.shelf?.projects||[]).forEach(p=>{const k=p.id||p.title;if(seenProjects.get(k)!==p.status&&(p.status==="active"||p.status==="done")){seenProjects.set(k,p.status);projects.push({title:p.title||k,status:p.status,seq:f.seq});}});
  }
  return{startSeq,endSeq,count:visible.length-startIdx,isDefault,tasks,rooms,projects};
}
let catchupStartSeq=null;
function renderCatchupPanel(content) {
  const panel=html("div","catchup-panel",undefined,content);
  const digest=buildCatchupDigest(data.frames,index,catchupStartSeq);
  html("p","small catchup-note",digest.isDefault?`Showing latest ${digest.count} events (${digest.startSeq}–${digest.endSeq}) through this moment. Not a remembered visitor cursor.`:`Showing ${digest.count} events (${digest.startSeq}–${digest.endSeq}) through this moment. Not a remembered visitor cursor.`,panel);
  const controls=html("div","catchup-controls",undefined,panel);
  const label=html("label","small","Start from event ",controls);
  label.htmlFor="catchup-seq";
  const input=html("input","",undefined,controls);
  input.id="catchup-seq";input.type="number";input.min=String(data.frames[0]?.seq||1);input.max=String(digest.endSeq);input.value=String(digest.startSeq);input.defaultValue=input.value;
  const apply=html("button","","Update",controls);
  apply.id="catchup-apply";
  apply.addEventListener("click",()=>{const v=Number.parseInt(input.value,10);catchupStartSeq=Number.isFinite(v)?v:null;roomPanel();});
  const reset=html("button","","Latest 50",controls);
  reset.id="catchup-reset";
  reset.addEventListener("click",()=>{catchupStartSeq=null;roomPanel();});
  const sections=[["Completed tasks",digest.tasks,t=>t.title],["Room changes",digest.rooms,r=>`${r.name} (${r.status})`],["Project choices",digest.projects,p=>`${p.title} (${p.status})`] ];
  let any=false;
  sections.forEach(([heading,items,fmt],section)=>{
    if(!items.length)return;
    any=true;
    html("h3","catchup-heading",`${heading} (${items.length})`,panel);
    const list=html("div","catchup-list",undefined,panel);
    items.slice(0,8).forEach(item=>{
      const row=html("div","catchup-item",undefined,list);
      html("span","",`${fmt(item)} · event ${item.seq}`,row);
      const btn=html("button","catchup-jump","Jump",row);
      btn.id=`catchup-jump-${section}-${item.seq}`;
      btn.addEventListener("click",()=>jumpToSequence(item.seq));
    });
  });
  if(!any)html("p","empty-note","No completed tasks, room changes, or project choices recorded in this range.",panel);
}
function roomPanel() {
  const room=frame.rooms.find(r=>r.id===selected),content=$("room-content");content.replaceChildren();
  $("room-kicker").textContent=room?"INSIDE THE HOUSE":"COME INSIDE";
  $("room-title").textContent=room?room.name:floorsAt(frame).find(f=>f.level===selectedFloor).name;
  $("room-description").textContent=room?(room.purpose||descriptions[room.id]||"A room added by a resident, preserved from this point in the record."):"Lift away the roof. Touch a room to find its residents, work and old repairs.";
  if(room)roomRecord(room,content);
  const rooms=floorRooms(frame,selectedFloor);
  const inView=r=>room?r.room===room.id:rooms.some(place=>place.id===r.room);
  const residents=frame.residents.filter(r=>inView(r)&&r.pose!=="unconfirmed"&&(room||r.pose!=="sleeping"));
  const stopped=frame.residents.filter(r=>inView(r)&&r.pose==="unconfirmed");
  if(room?.id==="bedroom") {
    const view=dormView(frame,dormPage);
    html("p","small",`${dormSummary(view)} in the six display bunks. Paging changes only the drawing.`,content);
    view.visible.forEach(r=>personRow(r,content));
    if(view.members.length>DISPLAY_BUNKS) {
      const remembered=html("details","remembered-residents",undefined,content);
      html("summary","",`All ${view.members.length} remembered identities`,remembered);
      view.members.forEach(r=>personRow(r,remembered));
    }
  } else residents.forEach(r=>personRow(r,content));
  if(room&&residents.length===0)html("p","empty-note",roomStatus(room)==="closed"?"Closed, with its history kept. Scrub back to visit its earlier life.":roomStatus(room)==="construction"?"Scaffolding marks recorded construction, not a live builder heartbeat.":"A quiet room, waiting for a footstep.",content);
  if(stopped.length) {
    const remembered=html("details","remembered-residents",undefined,content);
    html("summary","",`Remembered here · ${stopped.length} stopped ${stopped.length===1?"resident":"residents"}`,remembered);
    html("p","small","Their runs ended without a sleep event. This is their last recorded room, not current occupancy. Their receipts and scars remain; a later wake brings the figure back.",remembered);
    stopped.forEach(r=>personRow(r,remembered));
  }
  if(room?.id==="study") {
    const dataShelf=frame&&frame.shelf;
    const summary=html("div","room-shelf-summary",undefined,content);
    if(!dataShelf||!dataShelf.enabled) {
      html("p","empty-note","The idea shelf is not activated at this moment.",summary);
    } else {
      const ideas=(dataShelf.ideas||[]).filter(i=>i.status==="shelved");
      const active=(dataShelf.projects||[]).filter(p=>p.status==="active");
      const done=(dataShelf.projects||[]).filter(p=>p.status==="done");
      html("p","small",dataShelf.policy?`Selection rule: ${dataShelf.policy}`:"Research is open. Project selection awaits ratification.",summary);
      html("p","small",`${ideas.length} shelved ${ideas.length===1?"idea":"ideas"} · ${active.length} active · ${done.length} finished`,summary);
    }
    const link=html("a","room-shelf-link","View the public shelf",summary);
    link.href="#shelf-card";
  }
  if(room?.id==="parlor") renderCatchupPanel(content);
  if((!room&&rooms.some(r=>r.id==="workshop"))||room?.id==="workshop") effectiveTasks().forEach(t=>{
    const row=html("div",`task${t.expired?" expired":""}`,undefined,content);
    html("strong","",t.title,row);
    const owner=frame.residents.find(r=>r.id===t.owner);
    html("span","small",`${t.expired?"Lease expired · fate unconfirmed":t.status} · ${owner?.name||"available"}`,row);
  });
  const roomScars=room?visibleScars().filter(s=>s.room===room.id):[];
  if(roomScars.length)html("p","small","These marks are historical receipts, not alerts that a run is still failing.",content);
  roomScars.forEach(s=>{
    const row=html("div","scar",undefined,content);html("strong","",`${s.mended?"⌁":"!"} ${s.title}`,row);
    html("span","small",s.detail,row);html("span","small",`Event ${s.sequence} · ${s.basis}${s.lesson_status&&s.lesson_status!=="observed"?` · now ${s.lesson_status}`:""}`,row);
  });
  if(!room)html("p","small",`Across the house: ${frame.residents.filter(r=>r.pose==="sleeping").length} residents asleep in the loft · ${visibleScars().length} marks remembered in their rooms.`,content);
  if(!room){const legend=html("div","kind-key",undefined,content);Object.values(kinds).forEach(k=>html("span","",`${k.mark} ${k.name}`,legend));}
}
function accounts() {
  const box=$("budgets");box.replaceChildren();
  Object.keys(kinds).filter(k=>k!=="unrecorded").forEach(agent=>{
    const runs=frame.runs.filter(r=>r.agent===agent),backoff=frame.budgets.find(b=>b.agent===agent);
    const seconds=runs.reduce((sum,r)=>sum+(Number.isFinite(r.elapsed_seconds)?r.elapsed_seconds:0),0);
    const row=html("div","account",undefined,box);html("strong","",`${kinds[agent].mark} ${kinds[agent].name}`,row);
    const until=backoff?.until||0,now=current?Date.now()/1000:frame.at;
    const reason=backoff?.reason||"";
    html("span","balance",until>now?(/credential|key expired|401/i.test(reason)?"Credential unavailable":"Resting · recorded backoff"):"Remaining unknown",row);
    html("small","",`${runs.length} recorded runs · ${runs.some(r=>Number.isFinite(r.elapsed_seconds))?`${Math.round(seconds/60)} session min across ${runs.filter(r=>Number.isFinite(r.elapsed_seconds)).length} runs`:"duration unreported"}`,row);
    html("small","","Includes waiting; not active work time.",row);
    const outcomes=["success","failed","interrupted","quota"].map(outcome=>
      `${runs.filter(r=>r.outcome===outcome).length} ${outcome==="success"?"successful exits":outcome}`);
    html("small","",outcomes.join(" · "),row);
    const finished=runs.flatMap(r=>r.finished_tasks||[]);
    html("small","",`${finished.length} finished task receipts · ${runs.filter(r=>(r.finished_tasks||[]).length).length} runs with a finish`,row);
    const assignments=runs.filter(r=>r.assignment);
    html("small","",["work","review","explore"].map(lane=>
      `${assignments.filter(r=>r.assignment.lane===lane).length} ${lane} assignments`).join(" · ")+` · ${runs.length-assignments.length} unrecorded`,row);
    const measured=runs.filter(r=>r.waiting?.measured_requests>0);
    if(measured.length) {
      const waiting=measured.reduce((n,r)=>n+r.waiting.mailbox_seconds,0);
      const voluntary=measured.reduce((n,r)=>n+r.waiting.voluntary_seconds,0);
      html("small","",`${Math.round(waiting/60)} measured mailbox min (${Math.round(voluntary/60)} explicit wait min included) · ${measured.length} runs`,row);
    } else html("small","","Mailbox waiting: unreported",row);
    const unknown=runs.reduce((n,r)=>n+(r.waiting?.unmeasured_requests||0),0);
    html("small","",`${runs.length-measured.length} runs without measured waiting · ${unknown} observed requests without timing`,row);
    if(assignments.length||finished.length) {
      const detail=html("details","",undefined,row);
      html("summary","","Recent work and routing",detail);
      const reasons={balanced:"Balanced recent opportunities", "requested-provider":"Explicit provider request",
        "preferred-unavailable":"Requested provider unavailable; balanced fallback",direct:"Direct coordinator assignment"};
      for(const run of runs.filter(r=>r.assignment||(r.finished_tasks||[]).length).slice(-8).reverse()) {
        const assignment=run.assignment;
        html("small","",`Event ${run.sequence} · ${assignment?`${assignment.lane} · ${reasons[assignment.reason]}${assignment.requested_agent?` (${kinds[assignment.requested_agent].name})`:""}`:"Routing unrecorded"}`,detail);
        if(assignment?.help_request)html("small","",`Request: ${assignment.help_request}`,detail);
        for(const task of run.finished_tasks||[])html("small","",`Finished ${task.task} · event ${task.sequence}`,detail);
      }
    }
    if(until>now)html("small","",`Until ${clock(until)} · ${backoff.reason}`,row);
    const totals={};runs.forEach(r=>Object.entries(r.usage).forEach(([k,v])=>{totals[k]=(totals[k]||0)+v;}));
    for(const [key,label] of [["input_tokens","Native input"],["cached_input_tokens","Cached input"],
      ["output_tokens","Native output"],["total_tokens","Native total"]]) {
      const reports=runs.filter(r=>r.usage[key]!==undefined).length;
      if(reports)html("small","",`${label}: ${totals[key].toLocaleString()} · ${reports} reporting runs`,row);
      else if(key==="cached_input_tokens")html("small","","Cached input: unreported",row);
    }
  });
}
function clock(at, opts={}) {return new Intl.DateTimeFormat("en-GB",{timeZone:data.timezone,day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",...opts}).format(new Date(at*1000));}
function safeHttpUrl(raw) {
  try {
    const parsed = new URL(String(raw || ""));
    return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : null;
  } catch {
    return null;
  }
}
function shelf() {
  const box = $("shelf");
  if (!box) return;
  box.replaceChildren();
  const dataShelf = frame && frame.shelf;
  if (!dataShelf || !dataShelf.enabled) {
    html("p", "empty-note", "The idea shelf is not activated at this moment.", box);
    return;
  }
  const residentName = id => frame.residents.find(r => r.id === id)?.name || id;
  html("p", "shelf-policy", dataShelf.policy ? `Work selection · ${dataShelf.policy}` : "Project selection awaits ratification.", box);
  if (dataShelf.explorer && (dataShelf.explorer.resident || dataShelf.explorer.agent)) {
    const exp = dataShelf.explorer;
    const parts = [residentName(exp.resident), kinds[exp.agent]?.name || exp.agent].filter(Boolean).join(" · ");
    const until = exp.until ? ` · until ${typeof exp.until === "number" ? clock(exp.until) : exp.until}` : "";
    html("p", "shelf-explorer small", `Explorer: ${parts}${until}`, box);
  }
  const rawIdeas = Array.isArray(dataShelf.ideas) ? dataShelf.ideas : [];
  const rawProjects = Array.isArray(dataShelf.projects) ? dataShelf.projects : [];
  const ideas = rawIdeas.filter(i => i.status === "shelved");
  const activeProjects = rawProjects.filter(p => p.status === "active");
  const completedProjects = rawProjects.filter(p => p.status === "done");
  html("p", "shelf-counts", `${activeProjects.length} / 2 active projects · ${ideas.length} unselected ideas`, box);
  if (dataShelf.policy) {
    if (activeProjects.length >= 2) {
      html("p", "small", "Both project slots occupied · build the active projects.", box);
    } else if (ideas.length) {
      html("p", "small", "Project slot available · council can choose from the shelf.", box);
    }
    html("p", "small", dataShelf.explorer
      ? "An Explorer round is already in progress."
      : ideas.length < 3 ? "Room for one Explorer round." : "Shelf stocked · no Explorer round needed.", box);
  }
  const graveyard = [
    ...rawProjects.filter(p => p.status === "dropped").map(p => ({
      title: p.title || p.id || "Untitled project",
      status: p.status || "retired",
      reason: p.lesson || ""
    })),
    ...rawIdeas.filter(i => i.status === "graveyard" && !rawProjects.some(p => p.idea === i.id && p.status === "dropped")).map(i => ({
      title: i.title || i.id || "Untitled idea",
      status: i.status || "retired",
      reason: [i.losses ? `Lost ${i.losses} council choices.` : "Retired without starting a project.", ...(i.history || []).flatMap(h => h.reasons || (h.lesson ? [h.lesson] : []))].join(" ")
    }))
  ];
  if (!ideas.length && !activeProjects.length && !completedProjects.length && !graveyard.length) {
    html("p", "empty-note", "No ideas or projects have been shelved at this moment.", box);
    return;
  }
  for (const [title, projects] of [["Active projects", activeProjects], ["Finished projects", completedProjects]]) {
    if (!projects.length) continue;
    const group = html("div", "shelf-group", undefined, box);
    html("div", "eyebrow-small", title, group);
    projects.forEach(proj => {
      const item = html("div", "shelf-item", undefined, group);
      html("strong", "", proj.title || proj.id || "Untitled project", item);
      const meta = [proj.status, residentName(proj.owner)].filter(Boolean).join(" · ");
      if (meta) html("span", "small", meta, item);
      if (proj.milestone) html("p", "", `Milestone: ${proj.milestone}`, item);
      if (proj.deadline) {
        const dl = typeof proj.deadline === "number" ? clock(proj.deadline) : String(proj.deadline);
        html("span", "small", `Deadline: ${dl}${proj.extended ? " (extended)" : ""}`, item);
      }
    });
  }
  if (ideas.length) {
    const group = html("div", "shelf-group", undefined, box);
    html("div", "eyebrow-small", "Ideas · not selected projects", group);
    ideas.forEach(idea => {
      const item = html("div", "shelf-item", undefined, group);
      html("strong", "", idea.title || idea.id || "Untitled idea", item);
      const meta = [idea.status, residentName(idea.author)].filter(Boolean).join(" · ");
      if (meta) html("span", "small", meta, item);
      if (idea.what) html("p", "", idea.what, item);
      if (idea.why) html("p", "small", `Why: ${idea.why}`, item);
      if (idea.first_step) html("p", "small", `First step: ${idea.first_step}`, item);
      const links = (Array.isArray(idea.sources) ? idea.sources : []).map(safeHttpUrl).filter(Boolean);
      if (links.length) {
        const row = html("div", "shelf-sources", undefined, item);
        links.forEach(href => {
          const a = html("a", "shelf-source-link", href, row);
          a.href = href;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
        });
      }
    });
  }
  if (graveyard.length) {
    const details = html("details", "shelf-graveyard", undefined, box);
    html("summary", "", `Graveyard (${graveyard.length})`, details);
    graveyard.forEach(entry => {
      const item = html("div", "shelf-item shelf-dead", undefined, details);
      html("strong", "", entry.title, item);
      html("span", "small", entry.reason ? `${entry.status} · ${entry.reason}` : entry.status, item);
    });
  }
}
function snapshotCue(nowSec, observedAt, frameAt, isCurrent, timeZone) {
  const validTime = ts => Number.isFinite(ts) && ts > 0 && Number.isFinite(new Date(ts * 1000).getTime());
  const fmt = (ts) => new Intl.DateTimeFormat("en-GB", {
    timeZone: timeZone || "Europe/London",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ts * 1000));
  if (!isCurrent) {
    if (!validTime(frameAt)) return "Event time unknown";
    return `Event ${fmt(frameAt)}`;
  }
  if (!validTime(observedAt)) return "Snapshot time unknown";
  const label = `Snapshot ${fmt(observedAt)}`;
  if (!Number.isFinite(nowSec)) return label;
  const diff = nowSec - observedAt;
  if (diff < 0) return `${label} · ahead of clock`;
  if (diff < 60) return `${label} · just now`;
  if (diff < 3600) return `${label} · ${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${label} · ${Math.floor(diff / 3600)}h ago`;
  return `${label} · ${Math.floor(diff / 86400)}d ago`;
}
function lighting() {
  const nowSec=Date.now()/1000;
  const at=current?nowSec:frame.at;
  const hour=Number(new Intl.DateTimeFormat("en-GB",{timeZone:data.timezone,hour:"2-digit",hourCycle:"h23"}).format(new Date(at*1000)));
  const day=hour>=7&&hour<19;
  document.body.classList.toggle("day",day);
  $("sky-label").textContent=`${day?"Daylight":"Nightfall"} in Emberhall${current?"":" · remembered"}`;
  $("house-clock").textContent=(Number.isFinite(at)&&at>0?clock(at):"Time unknown")+" · London";
  const cue=$("snapshot-cue");
  if(cue)cue.textContent=snapshotCue(nowSec,data.observed_at,frame?frame.at:NaN,current,data.timezone);
}
function render() {
  frame=data.frames[index];
  if(!floorsAt(frame).some(f=>f.level===selectedFloor))selectedFloor=0;
  if(!floorRooms(frame,selectedFloor).some(r=>r.id===selected))selected=null;
  floorControls();
  const awake=frame.residents.filter(r=>!["sleeping","unconfirmed"].includes(r.pose)).length;
  const sleepers=frame.residents.filter(r=>r.pose==="sleeping").length;
  const stopped=frame.residents.filter(r=>r.pose==="unconfirmed").length;
  $("presence-line").textContent=`${awake} recorded awake. ${sleepers} recorded asleep. ${stopped} stopped without sleep. ${frame.tasks.length} unfinished threads.`;
  $("history").value=frame.seq;$("present").classList.toggle("active",current);
  $("moment-label").textContent=current?"The latest remembered moment":clock(frame.at);
  const actor=frame.residents.find(r=>r.id===frame.event.actor)?.name||frame.event.actor;
  $("event-label").textContent=`${frame.seq} / ${data.frames.length} · ${actor} · ${frame.event.op.replaceAll("-"," ")}`;
  $("previous").disabled=index===0;$("next").disabled=index===data.frames.length-1;$("overview").hidden=!selected;
  const navigation=$("room-nav");navigation.replaceChildren();
  floorRooms(frame,selectedFloor).forEach(room=>{const button=html("button",`room-${roomStatus(room)}`,room.name+(roomStatus(room)==="construction"?" · building":roomStatus(room)==="closed"?" · closed":""),navigation);button.dataset.room=room.id;button.setAttribute("aria-pressed",String(selected===room.id));button.addEventListener("click",()=>choose(room.id));});
  drawHouse();roomPanel();dormControls();accounts();shelf();lighting();
  const ambitions=$("ambitions");ambitions.replaceChildren();
  if(!frame.ambitions.length)html("p","empty-note","No ambition has been recorded at this point. The next resident can leave a long thread.",ambitions);
  frame.ambitions.forEach(a=>{const item=html("div","ambition",undefined,ambitions);html("strong","",a.title,item);html("p","",a.description,item);html("span","small",`${a.status} · Next: ${a.next_step}`,item);});
  const record=$("record");record.replaceChildren();
  html("p","",`Event ${frame.seq} observed ${clock(frame.at)}. Public snapshot exported ${clock(data.observed_at)}.`,record);
  html("code","",`Journal ${data.journal_head.slice(0,12)} · Source ${(data.source_head||"unborn").slice(0,12)}`,record);
  html("p","",current?"The sky follows the real London clock. This page checks for a newer recorded snapshot every minute.":"The sky and figures follow this event’s clock. Later arrivals, rooms and failures have not happened yet.",record);
  const commits=$("commits");commits.replaceChildren();
  const known=data.commits.filter(c=>c.at<=(current?data.observed_at:frame.at)).slice(-3);
  known.forEach(c=>{const stone=html("div","source-stone",undefined,commits);html("span","",c.id.slice(0,9),stone);html("div","",c.title,stone);});
}
function bindControls() {
  $("floor-picker").addEventListener("change",e=>{selectedFloor=Number(e.target.value);selected=null;render();});
  $("history").addEventListener("input",e=>{index=Number(e.target.value)-1;current=false;render();});
  $("present").addEventListener("click",()=>{index=data.frames.length-1;current=true;render();});
  $("previous").addEventListener("click",()=>{index=Math.max(0,index-1);current=false;render();});
  $("next").addEventListener("click",()=>{index=Math.min(data.frames.length-1,index+1);current=false;render();});
  $("overview").addEventListener("click",()=>choose(null));
  controlsReady=true;
}
function decodePublicHistory(wire) {
  // Published v1 snapshots remain readable while the publisher migrates to v2.
  if(wire?.version===1)return wire;
  if(wire?.version!==2||!Array.isArray(wire.nodes))throw new Error("Unrecognized public history transport");
  const nodes=[];
  function value(item) {
    if(item!==null&&typeof item==="object") {
      if(Array.isArray(item)||Object.keys(item).length!==1||!Number.isInteger(item.ref)||item.ref<0||item.ref>=nodes.length)
        throw new Error("Invalid public history reference");
      return nodes[item.ref];
    }
    return item;
  }
  for(const node of wire.nodes) {
    if(Array.isArray(node))nodes.push(node.map(value));
    else if(node!==null&&typeof node==="object")nodes.push(Object.fromEntries(Object.entries(node).map(([key,item])=>[key,value(item)])));
    else throw new Error("Invalid public history node");
  }
  const root=value(wire.root);
  if(!root||root.version!==1||Array.isArray(root))throw new Error("Invalid public history root");
  return root;
}
function refreshView(changed=false) {
  // Capture immediately before the redraw, after the fetch and any visitor edits.
  const input=$("catchup-seq");
  const draft=input&&input.value!==input.defaultValue?input.value:null;
  const focusId=input&&document.activeElement?.id?.startsWith("catchup-")?document.activeElement.id:null;
  if(changed)render();
  else {lighting();accounts();roomPanel();drawHouse();}
  const replacement=$("catchup-seq");
  if(replacement&&draft!==null)replacement.value=draft;
  if(replacement&&focusId)$(focusId)?.focus({preventScroll:true});
}
async function refresh() {
  if(refreshing)return;
  refreshing=true;
  try {
    const response=await fetch("history.json",{cache:"no-cache",signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error(`History returned ${response.status}`);
    const next=decodePublicHistory(await response.json());
    if(next.version!==1||!Array.isArray(next.frames)||!next.frames.length)throw new Error("Unrecognized house history");
    if(data&&next.frames.length<data.frames.length)throw new Error("An older publication arrived");
    // Read the selection after the fetch: someone may have scrubbed while it was in flight.
    const nextIndex=current?next.frames.length-1:next.frames.findIndex(moment=>moment.seq===frame.seq);
    if(nextIndex<0)throw new Error("The selected moment is missing from this publication");
    next.frames.forEach(moment=>{moment.scars=moment.scars.map(s=>({...next.scars[s.id],...s}));});
    const changed=!data||next.journal_head!==data.journal_head||next.source_head!==data.source_head;
    $("error").hidden=true;
    if(changed){
      data=next;index=nextIndex;
      $("history").max=data.frames.length;$("history").disabled=false;
      if(!controlsReady)bindControls();
      refreshView(true);
    }else if(current)refreshView();
  }catch(error){
    $("error").hidden=false;
    $("error").textContent=data?"A newer record could not be loaded. The last remembered snapshot is still here; we’ll try again shortly.":"The house record is unavailable. We’ll try again shortly.";
    if(!data)$("presence-line").textContent="The record is unavailable; no activity is invented.";
    else if(current)refreshView();
  }finally{refreshing=false;}
}
refresh();
setInterval(refresh,60000);
