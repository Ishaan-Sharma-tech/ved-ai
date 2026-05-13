import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import Widget from './Widget.jsx'

// Detect which window we are in
const urlParams = new URLSearchParams(window.location.search);
const isWidget = urlParams.get('window') === 'widget';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isWidget ? <Widget /> : <App />}
  </StrictMode>,
)
