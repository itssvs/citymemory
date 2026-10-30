import { useEffect } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents, ZoomControl } from 'react-leaflet'
import { usePrefs } from '../i18n'
import { scoreTone, TYPE_NAME } from '../ui'

// high = coral, medium = yellow, low = warm grey (matches the score chips)
const FILL = { high: '#f0675a', mid: '#f8d44c', '': '#8c877f' }
const EDGE = { high: '#c94a3e', mid: '#c9a21f', '': '#5f5b55' }

function Clicker({ onPick }) {
  useMapEvents({ click: (e) => onPick && onPick(e.latlng) })
  return null
}

function Attribution() {
  // plain text credit, no extra symbols
  const map = useMap()
  useEffect(() => { map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>') }, [map])
  return null
}

function FitTo({ assets }) {
  const map = useMap()
  const key = assets.map((a) => a.asset_id).join(',')
  useEffect(() => {
    if (assets.length > 1) map.fitBounds(assets.map((a) => [a.lat, a.lng]), { padding: [56, 56], maxZoom: 17 })
    else if (assets.length === 1) map.setView([assets[0].lat, assets[0].lng], 17)
  }, [key])
  return null
}

export function MapLegend({ plain = false }) {
  const { t } = usePrefs()
  if (plain) return (
    <div className="map-legend"><span><i style={{ background: FILL[''] }} />{t('known')}</span><span>{t('bigger')}</span></div>
  )
  return (
    <div className="map-legend">
      <span><i style={{ background: FILL.high }} />High priority</span>
      <span><i style={{ background: FILL.mid }} />Medium</span>
      <span><i style={{ background: FILL[''] }} />Low</span>
      <span>Bigger circle means more failures</span>
    </div>
  )
}

export default function AssetMap({ assets, selected, onSelect, pin, onPick, height = 460, fit = false, plain = false }) {
  const { t, lang } = usePrefs()
  const center = assets.length
    ? [assets.reduce((s, a) => s + a.lat, 0) / assets.length, assets.reduce((s, a) => s + a.lng, 0) / assets.length]
    : [13.0318, 80.1807]
  return (
    <MapContainer center={center} zoom={16} style={{ height, width: '100%' }} scrollWheelZoom={false} zoomControl={false}>
      <ZoomControl position="topright" />
      <Attribution />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Clicker onPick={onPick} />
      {fit && <FitTo assets={assets} />}
      {assets.map((a) => {
        const tone = plain ? '' : scoreTone(a.priority)
        const isSel = selected === a.asset_id
        return (
          <CircleMarker
            key={a.asset_id}
            center={[a.lat, a.lng]}
            radius={7 + Math.min(a.incident_count || 0, 10) * 1.7}
            pathOptions={{
              color: isSel ? '#26272b' : EDGE[tone], weight: isSel ? 3.5 : 1.5,
              fillColor: FILL[tone], fillOpacity: a.registered === 0 ? 0.35 : 0.85, dashArray: a.registered === 0 ? '4 3' : null,
            }}
            eventHandlers={{ click: () => onSelect && onSelect(a.asset_id) }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <b>{a.name}</b><br />
              {lang === 'ta' ? `${t(a.type)}, ${a.incident_count} முறை பழுது` : `${TYPE_NAME[a.type]}, ${a.incident_count} failure${a.incident_count === 1 ? '' : 's'}`}{plain ? '' : `, priority ${a.priority}`}
            </Tooltip>
          </CircleMarker>
        )
      })}
      {pin && (
        <CircleMarker center={[pin.lat, pin.lng]} radius={10} pathOptions={{ color: '#26272b', weight: 3, fillOpacity: 1, fillColor: '#f8d44c' }}>
          <Tooltip permanent direction="top" offset={[0, -8]}>{t('yourPin')}</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  )
}
