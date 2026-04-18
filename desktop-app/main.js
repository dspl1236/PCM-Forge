const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 720,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#0a0a0c',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    autoHideMenuBar: true,
    title: 'PCM-Forge'
  });

  mainWindow.loadFile('index.html');

  // Open external links in system browser, not inside the app
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file://')) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

// Serial port IPC handlers
ipcMain.handle('serial:list', async () => {
  try {
    const { SerialPort } = require('serialport');
    return await SerialPort.list();
  } catch (e) { return []; }
});

let activePort = null;

ipcMain.handle('serial:open', async (_, portPath, baudRate) => {
  try {
    const { SerialPort } = require('serialport');
    if (activePort && activePort.isOpen) activePort.close();
    activePort = new SerialPort({ path: portPath, baudRate: baudRate || 500000 });
    return { ok: true };
  } catch (e) { return { ok: false, error: e.message }; }
});

ipcMain.handle('serial:write', async (_, data) => {
  if (!activePort || !activePort.isOpen) return { ok: false, error: 'Port not open' };
  return new Promise(resolve => {
    activePort.write(Buffer.from(data), err => {
      resolve(err ? { ok: false, error: err.message } : { ok: true });
    });
  });
});

ipcMain.handle('serial:read', async (_, timeout) => {
  if (!activePort || !activePort.isOpen) return { ok: false, error: 'Port not open' };
  return new Promise(resolve => {
    const buf = [];
    const timer = setTimeout(() => {
      activePort.removeAllListeners('data');
      resolve({ ok: true, data: buf });
    }, timeout || 2000);
    activePort.on('data', chunk => {
      buf.push(...chunk);
    });
  });
});

ipcMain.handle('serial:close', async () => {
  if (activePort && activePort.isOpen) {
    activePort.close();
    activePort = null;
  }
  return { ok: true };
});
