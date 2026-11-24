import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Circle, CircleMarker, MapContainer, Marker, Polygon, TileLayer, Tooltip, ZoomControl, useMap, useMapEvents } from 'react-leaflet';
import { api } from '../api.js';
import { TILES } from '../config.js';
import { useLayerData } from '../hooks/useLayerData.js';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';
import Legend from './Legend.jsx';

const INDIA = [[5, 66], [38.5, 100]];
const PIN = L.divIcon({ className: 'pin', html: '<span class="pin__head"></span><span class="pin__tip"></span>', iconSize: [30, 40], iconAnchor: [15, 38] });

/** Keeps clicks/scrolls on our own overlay controls from reaching the map underneath. */
function Overlay({ className, children, ...rest }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) { L.DomEvent.disableClickPropagation(ref.current); L.DomEvent.disableScrollPropagation(ref.current); }
  }, []);
  return <div ref={ref} className={className} {...rest}>{children}</div>;
}

function Clicks({ onSelect, drawing, onBoundaryPoint }) {
  useMapEvents({ click: (e) => drawing ? onBoundaryPoint([e.latlng.lat, e.latlng.lng]) : onSelect({ lat: e.latlng.lat, lon: e.latlng.lng, source: 'map' }) });
  return null;
}

/** The map pane shrinks/grows with the page layout (bottom sheet on phones); tell Leaflet. */
function ResizeWatcher() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

function Focus({ focus }) {
  const map = useMap();
  useEffect(() => {
    if (!focus) return;
    const zoom = Math.max(map.getZoom(), focus.zoom || 13);
    map.flyTo([focus.lat, focus.lon], zoom, { duration: 0.8 });
  }, [focus, map]);
  return null;
}

/** Draws a GeoJSON FeatureCollection on a canvas (fast for thousands of cells) and removes it on change/unmount. */
function GeoLayer({ data, options }) {
  const map = useMap();
  useEffect(() => {
    if (!data) return undefined;
    const layer = L.geoJSON(data, { ...options, renderer: L.canvas({ padding: 0.3 }), interactive: false });
    layer.addTo(map);
    return () => { layer.remove(); };
  }, [map, data, options]);
  return null;
}

function Data({ layers, onHint }) {
  const map = useMap();
  const { meta, colorOf } = useMeta();
  const [view, setView] = useState({ bounds: map.getBounds(), zoom: map.getZoom() });
  useMapEvents({ moveend: () => setView({ bounds: map.getBounds(), zoom: map.getZoom() }) });
  const minZoom = meta?.min_zoom_for_potential_layer ?? 8;
  const potentialOn = layers.potential && view.zoom >= minZoom;
  const potential = useLayerData('potential', view.bounds, potentialOn);
  const wells = useLayerData('wells', view.bounds, layers.wells && view.zoom >= 9);
  const records = useLayerData('borewells', view.bounds, layers.records && view.zoom >= 10 && !!meta?.show_record_points);
  const [coverage, setCoverage] = useState(null);
  useEffect(() => {
    if (!layers.coverage) return undefined;
    const ac = new AbortController();
    api.coverage(ac.signal).then(setCoverage).catch(() => {});
    return () => ac.abort();
  }, [layers.coverage]);

  const truncated = !!potential.data?.truncated;
  useEffect(() => {
    onHint(layers.potential && view.zoom < minZoom ? 'zoomIn' : truncated ? 'zoomMore' : potential.status === 'error' ? 'layerError' : null);
  }, [layers.potential, view.zoom, minZoom, truncated, potential.status, onHint]);

  const potentialOpts = useMemo(() => ({
    style: (f) => ({ stroke: false, fillColor: colorOf(f.properties.class), fillOpacity: 0.5 }),
  }), [colorOf]);
  const wellOpts = useMemo(() => ({
    pointToLayer: (_f, ll) => L.circleMarker(ll, { radius: 4.5, color: '#2B1B57', weight: 1.6, fillColor: '#fff', fillOpacity: 1 }),
  }), []);
  const recordOpts = useMemo(() => ({
    pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 3, weight: 1.3, color: '#4B5963', fillColor: '#4B5963', fillOpacity: f.properties.outcome === 'dry' ? 0 : 0.9 }),
  }), []);
  const coverageOpts = useMemo(() => ({ style: { color: '#6A4FC4', weight: 1.5, dashArray: '6 6', fill: false } }), []);

  return (
    <>
      {potentialOn && !truncated && <GeoLayer data={potential.data} options={potentialOpts} />}
      {layers.coverage && <GeoLayer data={coverage} options={coverageOpts} />}
      <GeoLayer data={wells.data} options={wellOpts} />
      <GeoLayer data={records.data} options={recordOpts} />
    </>
  );
}

export default function MapView({ point, onSelect, focus, drawing = false, boundary = [], candidates = [], onBoundaryPoint = () => {} }) {
  const { t } = useI18n();
  const { meta } = useMeta();
  const [base, setBase] = useState('street');
  const [layers, setLayers] = useState({ potential: true, wells: false, records: false, coverage: true });
  const [hint, setHint] = useState(null);
  const bounds = meta?.state?.coverage_bbox
    ? [[meta.state.coverage_bbox[1], meta.state.coverage_bbox[0]], [meta.state.coverage_bbox[3], meta.state.coverage_bbox[2]]]
    : meta?.state?.bounds || [[15.8, 77.2], [19.95, 81.8]];
  const tile = TILES[base];
  const toggle = (k) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  return (
    <div className="map" data-base={base}>
      <MapContainer bounds={bounds} maxBounds={INDIA} maxBoundsViscosity={0.7} minZoom={5} zoomControl={false}
        className="map__leaflet" keyboard preferCanvas>
        <TileLayer key={base} url={tile.url} attribution={tile.attribution} maxZoom={tile.maxZoom} />
        <ZoomControl position="topright" zoomInTitle={t('map.zoomIn')} zoomOutTitle={t('map.zoomOut')} />
        <ResizeWatcher />
        <Clicks onSelect={onSelect} drawing={drawing} onBoundaryPoint={onBoundaryPoint} />
        <Focus focus={focus} />
        <Data layers={layers} onHint={setHint} />
        {boundary.length >= 3 && <Polygon positions={boundary} pathOptions={{ color: '#6A4FC4', weight: 3, fillColor: '#8B75D7', fillOpacity: 0.16, dashArray: drawing ? '5 5' : undefined }} />}
        {candidates.map((candidate) => <CircleMarker key={candidate.id} center={[candidate.lat, candidate.lon]} radius={8} pathOptions={{ color: '#fff', weight: 2, fillColor: candidate.rank === 1 ? '#16834A' : '#315A9B', fillOpacity: 0.95 }}><Tooltip permanent>{`#${candidate.rank}`}</Tooltip></CircleMarker>)}
        {point && (
          <>
            {point.source === 'gps' && point.accuracy > 0 && <Circle center={[point.lat, point.lon]} radius={point.accuracy} pathOptions={{ color: '#6A4FC4', weight: 1, fillOpacity: 0.12 }} />}
            <Marker position={[point.lat, point.lon]} icon={PIN} draggable title={t('map.pinTitle')} alt={t('map.pinTitle')}
              eventHandlers={{ dragend: (e) => { const ll = e.target.getLatLng(); onSelect({ lat: ll.lat, lon: ll.lng, source: 'drag' }); } }} />
          </>
        )}
      </MapContainer>

      <Overlay className="map__tools">
        <div className="seg" role="group" aria-label={t('map.base')}>
          <button type="button" aria-pressed={base === 'street'} onClick={() => setBase('street')}>{t('map.street')}</button>
          <button type="button" aria-pressed={base === 'satellite'} onClick={() => setBase('satellite')}>{t('map.satellite')}</button>
        </div>
        <details className="layers">
          <summary>{t('map.layers')}</summary>
          <label><input type="checkbox" checked={layers.potential} onChange={() => toggle('potential')} /> {t('map.l.potential')}</label>
          <label><input type="checkbox" checked={layers.coverage} onChange={() => toggle('coverage')} /> {t('map.l.coverage')}</label>
          <label><input type="checkbox" checked={layers.wells} onChange={() => toggle('wells')} /> {t('map.l.wells')}</label>
          {meta?.show_record_points && <label><input type="checkbox" checked={layers.records} onChange={() => toggle('records')} /> {t('map.l.records')}</label>}
        </details>
      </Overlay>

      <Overlay className="map__legend"><Legend compact /></Overlay>
      {hint && <p className="map__hint" role="status">{t(`map.hint.${hint}`)}</p>}
    </div>
  );
}
