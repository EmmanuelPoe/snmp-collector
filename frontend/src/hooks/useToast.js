import React, { createContext, useContext } from 'react';

const ToastContext = createContext({ showToast: () => {} });

export function ToastProvider({ children }) {
  return <ToastContext.Provider value={{ showToast: () => {} }}>{children}</ToastContext.Provider>;
}

export function useToast() {
  return useContext(ToastContext);
}
