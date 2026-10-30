import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/manrope'
import '@fontsource-variable/noto-sans-tamil'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'
import { PrefsProvider } from './i18n'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <PrefsProvider>
      <App />
    </PrefsProvider>
  </StrictMode>,
)
