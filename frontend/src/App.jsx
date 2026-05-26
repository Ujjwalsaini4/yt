import React, { useState, useEffect, useRef } from 'react';

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [videoInfo, setVideoInfo] = useState(null);
  const [selectedRes, setSelectedRes] = useState('');
  
  // Download states
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [downloadSpeed, setDownloadSpeed] = useState('');
  const [eta, setEta] = useState('');
  const [totalSize, setTotalSize] = useState('');
  const [downloadStatus, setDownloadStatus] = useState('');
  const [finishedFile, setFinishedFile] = useState(null);
  
  // YouTube Bot Bypass States
  const [showSettings, setShowSettings] = useState(false);
  const [cookiesText, setCookiesText] = useState('');
  const [cookiesActive, setCookiesActive] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');
  
  const wsRef = useRef(null);

  // Fetch cookie status on mount
  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        setCookiesActive(data.cookies_active);
      }
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    }
  };

  const handleSaveCookies = async (e) => {
    e.preventDefault();
    setSaveSuccess('');
    setError('');
    
    try {
      const res = await fetch('/api/save-cookies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cookies: cookiesText }),
      });
      
      if (!res.ok) {
        throw new Error('Failed to save cookies.');
      }
      
      const data = await res.json();
      setSaveSuccess(data.message);
      setCookiesActive(!!cookiesText.trim());
      if (!cookiesText.trim()) {
        setCookiesText('');
      }
    } catch (err) {
      setError(err.message || 'An error occurred while saving cookies.');
    }
  };

  const handleClearCookies = async () => {
    setCookiesText('');
    setSaveSuccess('');
    setError('');
    
    try {
      const res = await fetch('/api/save-cookies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cookies: '' }),
      });
      
      if (!res.ok) {
        throw new Error('Failed to clear cookies.');
      }
      
      const data = await res.json();
      setSaveSuccess('Cookies cleared successfully.');
      setCookiesActive(false);
    } catch (err) {
      setError(err.message || 'An error occurred while clearing cookies.');
    }
  };

  // Auto-select the highest available resolution when videoInfo loads
  useEffect(() => {
    if (videoInfo && videoInfo.resolutions && videoInfo.resolutions.length > 0) {
      // Find highest video resolution (not audio)
      const videoOnly = videoInfo.resolutions.filter(r => r.id !== 'audio');
      if (videoOnly.length > 0) {
        setSelectedRes(videoOnly[0].id);
      } else {
        setSelectedRes(videoInfo.resolutions[0].id);
      }
    }
  }, [videoInfo]);

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleFetchInfo = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError('');
    setVideoInfo(null);
    setFinishedFile(null);
    setProgress(0);
    setDownloadStatus('');

    try {
      const response = await fetch('/api/info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch video details. Make sure the URL is valid.');
      }

      const data = await response.json();
      setVideoInfo(data);
    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred while fetching video info.');
    } finally {
      setLoading(false);
    }
  };

  const handleStartDownload = () => {
    if (!videoInfo || !selectedRes) return;

    setDownloading(true);
    setError('');
    setProgress(0);
    setDownloadSpeed('');
    setEta('');
    setTotalSize('');
    setDownloadStatus('Connecting to downloader...');

    // Setup WebSocket URL (works on local host and mobile network IP automatically)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/download`;
    
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      // Send parameters to start download
      const payload = {
        url: videoInfo.original_url,
        resolution: selectedRes
      };
      wsRef.current.send(JSON.stringify(payload));
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.status === 'starting') {
          setDownloadStatus(data.message);
        } else if (data.status === 'downloading') {
          setDownloadStatus('Downloading streams...');
          setProgress(data.percent || 0);
          
          // Format speed
          if (data.speed) {
            const mbSpeed = data.speed / (1024 * 1024);
            setDownloadSpeed(`${mbSpeed.toFixed(1)} MB/s`);
          } else {
            setDownloadSpeed('N/A');
          }
          
          // Format ETA
          if (data.eta) {
            const minutes = Math.floor(data.eta / 60);
            const seconds = data.eta % 60;
            setEta(minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`);
          } else {
            setEta('calculating...');
          }
          
          // Format size
          if (data.total_bytes) {
            const mbSize = data.total_bytes / (1024 * 1024);
            setTotalSize(`${mbSize.toFixed(1)} MB`);
          } else {
            setTotalSize('dynamic');
          }
        } else if (data.status === 'merging') {
          setDownloadStatus(data.msg || 'Processing video/audio tracks...');
          setProgress(98); // Set near full since downloading is done
          setDownloadSpeed('FFmpeg merging');
          setEta('processing...');
        } else if (data.status === 'merging_finished') {
          setDownloadStatus(data.msg || 'Wrapping up...');
          setProgress(99);
        } else if (data.status === 'completed') {
          setDownloadStatus('Completed');
          setProgress(100);
          setDownloading(false);
          setFinishedFile(data.filename);
          // Close websocket
          if (wsRef.current) wsRef.current.close();
        } else if (data.status === 'error') {
          setError(data.message || 'An error occurred during downloading.');
          setDownloading(false);
          if (wsRef.current) wsRef.current.close();
        }
      } catch (err) {
        console.error('WebSocket message parsing error:', err);
      }
    };

    wsRef.current.onerror = (err) => {
      console.error('WebSocket Error:', err);
      setError('Downloader connection interrupted.');
      setDownloading(false);
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket closed.');
    };
  };

  const handleReset = () => {
    setUrl('');
    setVideoInfo(null);
    setError('');
    setProgress(0);
    setDownloadStatus('');
    setFinishedFile(null);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '0:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header>
        <div className="logo-container">
          <div className="logo-icon">
            {/* SVG Logo: Vault / Shield with Download Arrow */}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="logo-svg" style={{width: '24px', height: '24px', color: '#fff'}}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m0 0l-3-3m3 3l3-3m-9-4H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V7a2 2 0 00-2-2h-7l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <span className="logo-text">StreamVault</span>
        </div>
        <p className="subtitle">Premium All-Platform 4K Video Downloader. Supports YouTube, TikTok, Instagram, Facebook, and more.</p>
      </header>

      {/* Error Toast */}
      {error && (
        <div className="toast">
          {/* SVG Warning Icon */}
          <svg className="toast-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* Main Search Panel */}
      {!videoInfo && !finishedFile && !downloading && (
        <div className="search-card">
          <form className="search-form" onSubmit={handleFetchInfo}>
            <div className="input-wrapper">
              {/* SVG Search Icon */}
              <svg className="input-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="url"
                className="search-input"
                placeholder="Paste video URL here (e.g. YouTube, Instagram, TikTok...)"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
                required
              />
            </div>
            <button type="submit" className="search-button" disabled={loading || !url}>
              {loading ? (
                <>
                  <div className="spinner"></div>
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <span>Fetch Info</span>
                  <svg style={{width: '20px', height: '20px'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </form>
        </div>
      )}

      {/* Settings Panel Content (Permanently Visible) */}
      {!videoInfo && !finishedFile && !downloading && (
        <div className="search-card" style={{ marginTop: '0rem', marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
            <span className="pulse-indicator" style={{ background: cookiesActive ? 'var(--accent-green)' : 'var(--text-muted)', boxShadow: cookiesActive ? '0 0 10px var(--accent-green)' : 'none' }}></span>
            Bypass YouTube Bot Check (Cookies)
            <span style={{ fontSize: '0.85rem', color: cookiesActive ? 'var(--accent-green)' : 'var(--text-muted)', fontWeight: 'normal', marginLeft: 'auto' }}>
              Status: {cookiesActive ? '🟢 Active' : '⚪ Off'}
            </span>
          </h3>
          
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4', marginBottom: '1rem' }}>
            YouTube sometimes blocks cloud server IPs with a bot detection screen. To bypass this, paste your browser's YouTube cookies in <strong>Netscape cookie format</strong> below.
            <br />
            <span style={{ fontSize: '0.75rem', display: 'inline-block', marginTop: '0.25rem', color: 'var(--accent-cyan)' }}>
              How to get: Install browser extension <em>"Get cookies.txt LOCALLY"</em>, open YouTube, export cookies, and copy/paste their content here.
            </span>
          </p>

          <form onSubmit={handleSaveCookies}>
            <textarea
              style={{
                width: '100%',
                height: '100px',
                background: 'rgba(8, 10, 20, 0.6)',
                border: '1px solid var(--glass-border)',
                borderRadius: '8px',
                padding: '0.75rem',
                color: '#fff',
                fontSize: '0.8rem',
                fontFamily: 'monospace',
                resize: 'vertical',
                outline: 'none',
                marginBottom: '0.75rem'
              }}
              placeholder="# Netscape HTTP Cookie File&#10;.youtube.com	TRUE	/	TRUE	1799999999	SID	..."
              value={cookiesText}
              onChange={(e) => setCookiesText(e.target.value)}
            />
            
            {saveSuccess && (
              <div style={{ fontSize: '0.85rem', color: 'var(--accent-green)', fontWeight: '600', marginBottom: '0.75rem' }}>
                ✓ {saveSuccess}
              </div>
            )}
            
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button 
                type="submit" 
                className="download-submit-button"
                style={{ width: 'auto', padding: '0.5rem 1.5rem', fontSize: '0.85rem', height: '36px', background: 'var(--primary-glow)' }}
              >
                Save Cookies
              </button>
              
              {cookiesActive && (
                <button 
                  type="button" 
                  onClick={handleClearCookies}
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--accent-rose)',
                    color: 'var(--accent-rose)',
                    borderRadius: '8px',
                    padding: '0.5rem 1.25rem',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    height: '36px'
                  }}
                >
                  Clear Cookies
                </button>
              )}
            </div>
          </form>
        </div>
      )}

      {/* Video Details Card */}
      {videoInfo && !downloading && !finishedFile && (
        <div className="preview-card">
          <div className="thumbnail-container">
            <img src={videoInfo.thumbnail} alt={videoInfo.title} className="thumbnail-image" />
            <span className="video-duration">{formatDuration(videoInfo.duration)}</span>
            <span className="video-platform-badge">{videoInfo.platform || 'video'}</span>
          </div>
          
          <div className="info-content">
            <h2 className="video-title" title={videoInfo.title}>{videoInfo.title}</h2>
            <div className="video-uploader">by @{videoInfo.uploader}</div>
            
            <div className="resolution-section">
              <div className="resolution-title">Select Quality</div>
              <div className="resolutions-grid">
                {videoInfo.resolutions.map((res) => (
                  <button
                    key={res.id}
                    className={`resolution-button ${selectedRes === res.id ? 'selected' : ''}`}
                    onClick={() => setSelectedRes(res.id)}
                  >
                    <span>{res.label}</span>
                    {res.id === 'audio' && <span className="quality-badge">MP3 Format</span>}
                    {res.id === '2160p' && <span className="quality-badge">Ultra HD 4K</span>}
                    {res.id === '1440p' && <span className="quality-badge">Quad HD 2K</span>}
                    {res.id === '1080p' && <span className="quality-badge">Full HD</span>}
                    {res.id === '720p' && <span className="quality-badge">HD</span>}
                    {res.id === 'best' && <span className="quality-badge">Best Dynamic</span>}
                  </button>
                ))}
              </div>
              
              <button className="download-submit-button" onClick={handleStartDownload}>
                <svg style={{width: '22px', height: '22px'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Download Now</span>
              </button>
              
              <button className="reset-button" onClick={handleReset}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Download Progress Card */}
      {downloading && (
        <div className="progress-card">
          <div className="progress-header">
            <span className="progress-status-title">
              <span className="pulse-indicator"></span>
              {downloadStatus}
            </span>
            <span className="progress-percentage">{Math.round(progress)}%</span>
          </div>
          
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
          </div>
          
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">
                <svg style={{width: '12px', height: '12px', marginRight: '4px', verticalAlign: 'middle'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Speed
              </div>
              <div className="stat-value">{downloadSpeed || 'connecting...'}</div>
            </div>
            
            <div className="stat-item">
              <div className="stat-label">
                <svg style={{width: '12px', height: '12px', marginRight: '4px', verticalAlign: 'middle'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                ETA
              </div>
              <div className="stat-value">{eta || 'calculating...'}</div>
            </div>
            
            <div className="stat-item">
              <div className="stat-label">
                <svg style={{width: '12px', height: '12px', marginRight: '4px', verticalAlign: 'middle'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
                Size
              </div>
              <div className="stat-value">{totalSize || 'analyzing...'}</div>
            </div>
          </div>
          
          <div className="progress-filename" title={videoInfo?.title}>
            Processing: {videoInfo?.title}
          </div>
        </div>
      )}

      {/* Success Alert */}
      {finishedFile && !downloading && (
        <div className="success-card">
          <div className="success-icon-container">
            <svg style={{width: '32px', height: '32px'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          
          <h2 className="success-title">Successfully Processed!</h2>
          <p className="success-message">
            {finishedFile}
            <br />
            <span style={{fontSize: '0.8rem', color: 'var(--accent-rose)', fontWeight: '600', display: 'inline-block', marginTop: '0.5rem'}}>
              ⚠️ Auto-deleting from server in 2 minutes to free space. Please save it now!
            </span>
          </p>
          
          {/* Dynamically hit the backend download-file API endpoint */}
          <a
            href={`/api/download-file/${encodeURIComponent(finishedFile)}`}
            className="download-link-btn"
            download
          >
            <svg style={{width: '20px', height: '20px'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Save Video to Device
          </a>
          
          <button className="reset-button" onClick={handleReset}>Download Another Video</button>
        </div>
      )}

      {/* Quick Guide Panel */}
      {!videoInfo && !downloading && !finishedFile && (
        <div className="guide-card">
          <div className="guide-title">
            <svg style={{width: '20px', height: '20px', color: 'var(--primary-solid)'}} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>How to Download</span>
          </div>
          
          <div className="steps-list">
            <div className="step-card">
              <div className="step-number">1</div>
              <div className="step-text-title">Copy Link</div>
              <div className="step-desc">Copy the video URL from YouTube, Instagram, TikTok, Twitter, Facebook, or other platforms.</div>
            </div>
            
            <div className="step-card">
              <div className="step-number">2</div>
              <div className="step-text-title">Select Quality</div>
              <div className="step-desc">Paste the link above, fetch details, and choose your preferred download format (up to 4K).</div>
            </div>
            
            <div className="step-card">
              <div className="step-number">3</div>
              <div className="step-text-title">Save to Device</div>
              <div className="step-desc">Watch real-time progress. Once done, tap "Save Video to Device" to store it on your phone or computer.</div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer>
        <p>StreamVault local downloader. Bindable to LAN interfaces for local Wi-Fi sharing.</p>
        <p style={{marginTop: '0.5rem'}}><a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noreferrer">Powered by yt-dlp</a></p>
      </footer>
    </div>
  );
}
