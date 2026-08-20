window.addEventListener('error', (e) => {
  if (e.message && e.message.includes('ResizeObserver loop')) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return true;
  }
});
init(GRAPH_DATA);

function init(data){
  const activeKey = n => `${n.top}||${n.sub}`;
  let activeKeys = new Set();
  Object.entries(data.legend_tree).forEach(([top, subs]) => {
    subs.forEach(s => activeKeys.add(`${top}||${s.sub}`));
  });

  document.getElementById('counts').textContent =
    `${data.nodes.length} recursos · ${data.edges.length} dependencias`;

  // Hierarchical legend: top category header + indented sub rows
  const legendList = document.getElementById('legendList');
  const TOP_ORDER = ['Colegios', 'ETDH', 'Transversal'];
  TOP_ORDER.forEach(top => {
    const subs = data.legend_tree[top];
    if(!subs) return;
    const topTotal = subs.reduce((a,s) => a + s.count, 0);
    const topColor = data.top_colors[top];

    const header = document.createElement('div');
    header.className = 'legend-item legend-top';
    header.style.fontWeight = '700';
    header.style.marginTop = '8px';
    header.dataset.top = top;
    header.innerHTML = `<span class="dot" style="background:${topColor}; color:${topColor}"></span>
      <span class="legend-label">${top}</span><span class="legend-count">${topTotal}</span>`;
    header.onclick = () => toggleTop(top, header);
    legendList.appendChild(header);

    subs.forEach(s => {
      const key = `${top}||${s.sub}`;
      const row = document.createElement('div');
      row.className = 'legend-item';
      row.style.paddingLeft = '20px';
      row.dataset.key = key;
      row.innerHTML = `<span class="dot" style="background:${s.color}; color:${s.color}"></span>
        <span class="legend-label" style="font-size:11.5px;">${s.sub}</span><span class="legend-count">${s.count}</span>`;
      row.onclick = () => toggleSub(key, row);
      legendList.appendChild(row);
    });
  });

  function toggleSub(key, el){
    if(activeKeys.has(key)){ activeKeys.delete(key); el.classList.add('dimmed'); }
    else { activeKeys.add(key); el.classList.remove('dimmed'); }
    applyFilter();
  }
  function toggleTop(top, headerEl){
    const rows = legendList.querySelectorAll(`[data-key^="${top}||"]`);
    const anyActive = Array.from(rows).some(r => activeKeys.has(r.dataset.key));
    rows.forEach(r => {
      if(anyActive){ activeKeys.delete(r.dataset.key); r.classList.add('dimmed'); }
      else { activeKeys.add(r.dataset.key); r.classList.remove('dimmed'); }
    });
    headerEl.classList.toggle('dimmed', anyActive);
    applyFilter();
  }

  function nodeVisible(n){
    // visible if its dominant category is active, OR if any of its mixed categories is active
    if(n.pair_counts){
      return Object.keys(n.pair_counts).some(k => {
        const [t,s] = k.split(' | ');
        return activeKeys.has(`${t}||${s}`);
      });
    }
    return activeKeys.has(activeKey(n));
  }

  function applyFilter(){
    const updates = data.nodes.map(n => ({ id: n.id, hidden: !nodeVisible(n) }));
    nodesDS.update(updates);
    const edgeUpdates = data.edges.map((e,i) => ({
      id: i,
      hidden: !activeKeys.has(`${e.op_top}||${e.op_sub}`)
    }));
    edgesDS.update(edgeUpdates);
  }

  // vis-network datasets
  const nodesDS = new vis.DataSet(data.nodes.map(n => ({
    id: n.id,
    label: n.label,
    title: '',
    value: n.size,
    color: { background: n.color, border: n.color, highlight:{background:n.color, border:'#FF6A13'} },
    font: { color:'#2B1D19', size:12, face:'Inter', strokeWidth:3, strokeColor:'#FFFBF9' },
  })));

  const edgesDS = new vis.DataSet(data.edges.map((e,i) => ({
    id: i,
    from: e.from, to: e.to,
    color: { color: e.color, opacity: 0.7, highlight: e.color },
    width: 1.1,
    arrows: { to: { enabled: true, scaleFactor: 0.4 } },
    smooth: { type:'continuous', roundness: 0.35 },
  })));

  const container = document.getElementById('network');
  const network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, {
    nodes: { shape:'dot', borderWidth:1, shadow:false },
    edges: { shadow:false },
    physics: {
      solver:'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant:-70, springLength:110, springConstant:0.06, damping:0.6, avoidOverlap:0.6 },
      stabilization: { iterations: 250 }
    },
    interaction: { hover:true, tooltipDelay:120, hideEdgesOnDrag:true, navigationButtons:false },
    autoResize: false,
    height: '100%',
    width: '100%',
  });

  function sizeNetworkToContainer(){
    const rect = container.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width));
    const h = Math.max(1, Math.floor(rect.height));
    network.setSize(w + 'px', h + 'px');
    network.redraw();
  }
  sizeNetworkToContainer();
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(sizeNetworkToContainer, 100);
  });

  const byId = {}; data.nodes.forEach(n => byId[n.id] = n);
  const edgesByNode = {};
  data.nodes.forEach(n => edgesByNode[n.id] = { out: [], in: [] });
  data.edges.forEach(e => {
    edgesByNode[e.from] && edgesByNode[e.from].out.push(e);
    edgesByNode[e.to] && edgesByNode[e.to].in.push(e);
  });

  const detail = document.getElementById('detail');
  const tooltip = document.getElementById('tooltip');
  const EMPTY_STATE_HTML = detail.innerHTML;

  network.on('hoverNode', params => {
    const n = byId[params.node];
    const catCount = n.pair_counts ? Object.keys(n.pair_counts).length : 1;
    tooltip.style.display = 'block';
    tooltip.innerHTML = `<b>${n.label}</b><br>${catCount} categoría(s) · ${n.ops.length} operación(es)`;
  });
  network.on('blurNode', () => tooltip.style.display = 'none');
  network.on('mouseMove', params => {
    if(tooltip.style.display === 'block'){
      tooltip.style.left = (params.pointer.DOM.x + 16) + 'px';
      tooltip.style.top = (params.pointer.DOM.y + 12) + 'px';
    }
  });

  function selectNode(id){
    const n = byId[id];
    if(!n) return;
    network.selectNodes([id]);
    highlightNeighborhood(id);
    renderDetail(n, id);
  }

  network.on('click', params => {
    if(params.nodes.length > 0){
      selectNode(params.nodes[0]);
    } else {
      clearHighlight();
      detail.innerHTML = EMPTY_STATE_HTML;
    }
  });

  network.on('doubleClick', params => {
    if(params.nodes.length > 0){
      network.focus(params.nodes[0], { scale: 1.2, animation: true });
    }
  });

  function highlightNeighborhood(id){
    const connected = new Set([id]);
    edgesByNode[id].out.forEach(e => connected.add(e.to));
    edgesByNode[id].in.forEach(e => connected.add(e.from));

    const nodeUpdates = data.nodes.map(n => ({
      id: n.id,
      opacity: connected.has(n.id) ? 1 : 0.12,
    }));
    nodesDS.update(nodeUpdates);

    const edgeUpdates = data.edges.map((e,i) => ({
      id: i,
      hidden: !(e.from === id || e.to === id) && !activeKeys.has(`${e.op_top}||${e.op_sub}`),
      color: { color: e.color, opacity: (e.from === id || e.to === id) ? 0.95 : 0.05 },
    }));
    edgesDS.update(edgeUpdates);
  }

  function clearHighlight(){
    nodesDS.update(data.nodes.map(n => ({ id:n.id, opacity: 1 })));
    applyFilter();
  }

  document.getElementById('resetBtn').onclick = () => {
    network.unselectAll();
    clearHighlight();
    detail.innerHTML = EMPTY_STATE_HTML;
    network.fit({ animation: true });
  };

  function catColorOf(n){ return n.color; }

  function renderDetail(n, id){
    const catColor = n.color;
    let badges = '';
    if(n.pair_counts){
      badges = Object.entries(n.pair_counts).map(([k,c]) => {
        const [t,s] = k.split(' | ');
        const col = data.legend_tree[t] ? (data.legend_tree[t].find(x=>x.sub===s)||{}).color : catColor;
        return `<span class="node-badge" style="background:${col}22; color:${col}; border:1px solid ${col}55; margin-right:6px;">${t} · ${s} (${c})</span>`;
      }).join('');
    } else {
      badges = `<span class="node-badge" style="background:${catColor}22; color:${catColor}; border:1px solid ${catColor}55">${n.top} · ${n.sub}</span>`;
    }
    let html = `<div class="node-title">${n.label}</div>
      <div style="margin-bottom:12px;">${badges}</div>
      <div class="op-count">${n.ops.length} operación(es) en este recurso</div>
      <div class="op-list">`;
    n.ops.forEach(op => {
      html += `<div class="op-card">
        <span class="op-method m-${op.method}">${op.method}</span><span class="op-name">${op.name}</span>
        <div class="op-desc">${op.desc || ''}</div>
        <div class="op-url">${op.url}</div>
        ${op.requires_list_of_same_resource ? `<div class="op-needs-id">⚠ Requiere un <b>id</b> que se obtiene primero llamando a <b>${op.requires_list_of_same_resource}</b></div>` : ''}
      </div>`;
    });
    html += `</div>`;

    const outRel = edgesByNode[id].out;
    const inRel = edgesByNode[id].in;

    if(outRel.length){
      html += `<div class="rel-section"><div class="rel-title">Este recurso depende de →</div>`;
      outRel.forEach(e => {
        const t = byId[e.to];
        html += `<div class="rel-item">
          <span class="rel-param">${e.label}</span><span class="rel-arrow">→</span>
          <span class="rel-target" data-goto="${e.to}" style="color:${t?t.color:'#2B1D19'}">${t?t.label:e.to}</span>
        </div>`;
      });
      html += `</div>`;
    }
    if(inRel.length){
      html += `<div class="rel-section"><div class="rel-title">← Recursos que dependen de este</div>`;
      inRel.forEach(e => {
        const s = byId[e.from];
        html += `<div class="rel-item">
          <span class="rel-target" data-goto="${e.from}" style="color:${s?s.color:'#2B1D19'}">${s?s.label:e.from}</span>
          <span class="rel-arrow">→</span><span class="rel-param">${e.label}</span>
        </div>`;
      });
      html += `</div>`;
    }
    if(!outRel.length && !inRel.length){
      html += `<div class="rel-section"><div class="hint">Sin dependencias de parámetros detectadas hacia/desde otros recursos.</div></div>`;
    }

    detail.innerHTML = html;
    detail.querySelectorAll('[data-goto]').forEach(el => {
      el.onclick = () => selectNode(el.dataset.goto);
    });
  }

  // search
  const searchInput = document.getElementById('search');
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if(!q){ clearHighlight(); return; }
    const matches = data.nodes.filter(n =>
      n.label.toLowerCase().includes(q) ||
      n.ops.some(o => o.name.toLowerCase().includes(q) || o.url.toLowerCase().includes(q))
    ).map(n => n.id);
    const matchSet = new Set(matches);
    nodesDS.update(data.nodes.map(n => ({ id:n.id, opacity: matchSet.has(n.id) ? 1 : 0.08 })));
    edgesDS.update(data.edges.map((e,i) => ({ id:i, color:{ color:e.color, opacity: (matchSet.has(e.from)||matchSet.has(e.to)) ? 0.7 : 0.03 } })));
    if(matches.length === 1){ network.focus(matches[0], {scale:1.1, animation:true}); }
  });

  network.once('stabilizationIterationsDone', () => { sizeNetworkToContainer(); network.fit(); });

  // Safety net: force a resize + fit shortly after mount in case the initial
  // container measurement in the sandboxed iframe was taken before layout settled.
  setTimeout(() => { sizeNetworkToContainer(); network.fit(); }, 300);
  setTimeout(() => { sizeNetworkToContainer(); network.fit(); }, 1000);
}
