const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('serial', {
  list: () => ipcRenderer.invoke('serial:list'),
  open: (port, baud) => ipcRenderer.invoke('serial:open', port, baud),
  write: (data) => ipcRenderer.invoke('serial:write', data),
  read: (timeout) => ipcRenderer.invoke('serial:read', timeout),
  close: () => ipcRenderer.invoke('serial:close')
});
