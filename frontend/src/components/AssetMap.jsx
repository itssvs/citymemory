import { useEffect } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { level, TYPE_ICON } from '../api'

const COLORS = { high: '#c0392b', mid: '#d68910', low: '#5d6d7e' }

function Clicker({ onPick }) {
  useMapEvents({ click: (e) => onPick && onPick(e.latlng) })
  return null
}

function FitTo({ assets }) {
  const map = useMap()
  const key = assets.map((a) => a.asset_id).join(',')
  useEffect(() => {
    if (assets.length > 1) map.fitBounds(assets.map((a) => [a.lat, a.lng]), { padding: [30, 30], maxZoom: 17 })
    else if (assets.length === 1) map.setView([assets[0].lat, assets[0].lng], 17)
  }, [key])
  return null
}

export default function AssetMap({ assets, selected, onSelect, pin, onPick, height = 460, fit = false }) {
  const center = assets.length
    ? [assets.reduce((s, a) => s + a.lat, 0) / assets.length, assets.reduce((s, a) => s + a.lng, 0) / assets.length]
    : [13.0318, 80.1807]
  return (
    <MapContainer center={center} zoom={16} style={{ height, width: '100%' }} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Clicker onPick={onPick} />
      {fit && <FitTo assets={assets} />}
      {assets.map((a) => {
        const lv = level(a.priority)
        const isSel = selected === a.asset_id
        return (
          <CircleMarker
            key={a.asset_id}
            center={[a.lat, a.lng]}
            radius={6 + Math.min(a.incident_count, 10) * 1.6}
            pathOptions={{
              color: isSel ? '#111' : COLORS[lv],
              weight: isSel ? 3 : 1.5,
              fillColor: COLORS[lv],
              fillOpacity: a.registered ? 0.45 : 0.15,
              dashArray: a.registered ? null : '4 3',
            }}
            eventHandlers={{ click: () => onSelect && onSelect(a.asset_id) }}
          >
            <Tooltip>
              <strong>{a.asset_id}</strong> · {TYPE_ICON[a.type]}
              <br />
              {a.name}
              <br />
              {a.incident_count} failures · priority {a.priority}
            </Tooltip>
          </CircleMarker>
        )
      })}
      {pin && (
        <CircleMarker center={[pin.lat, pin.lng]} radius={9} pathOptions={{ color: '#1a5276', weight: 3, fillOpacity: 0.9, fillColor: '#2e86c1' }}>
          <Tooltip permanent direction="top">Your pin</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  )
}
