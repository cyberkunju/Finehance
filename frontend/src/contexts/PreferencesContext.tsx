/**
 * Preferences Context
 *
 * Provides user preferences (currency, date format, notifications)
 * across the entire application. Persisted in localStorage.
 */

import React, { createContext, useContext, useState, useCallback } from 'react';

export interface UserPreferences {
  currency: string;
  dateFormat: string;
  emailNotifications: boolean;
  budgetAlerts: boolean;
  weeklyReports: boolean;
}

interface PreferencesContextType {
  preferences: UserPreferences;
  updatePreference: <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) => void;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  formatCurrency: (amount: number) => string;
  formatDate: (dateString: string) => string;
  getCurrencySymbol: () => string;
}

const PREFERENCES_KEY = 'ai-finance-preferences';

const defaultPreferences: UserPreferences = {
  currency: 'USD',
  dateFormat: 'MM/DD/YYYY',
  emailNotifications: true,
  budgetAlerts: true,
  weeklyReports: false,
};

// Currency → locale map for Intl.NumberFormat
const currencyLocaleMap: Record<string, string> = {
  USD: 'en-US',
  EUR: 'de-DE',
  GBP: 'en-GB',
  JPY: 'ja-JP',
  INR: 'en-IN',
  CAD: 'en-CA',
  AUD: 'en-AU',
  CHF: 'de-CH',
  CNY: 'zh-CN',
  KRW: 'ko-KR',
  BRL: 'pt-BR',
  MXN: 'es-MX',
};

// Currency → symbol map
const currencySymbolMap: Record<string, string> = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  INR: '₹',
  CAD: 'C$',
  AUD: 'A$',
  CHF: 'CHF',
  CNY: '¥',
  KRW: '₩',
  BRL: 'R$',
  MXN: 'MX$',
};

// Date format → Intl options map
const dateFormatOptions: Record<string, Intl.DateTimeFormatOptions> = {
  'MM/DD/YYYY': { month: '2-digit', day: '2-digit', year: 'numeric' },
  'DD/MM/YYYY': { day: '2-digit', month: '2-digit', year: 'numeric' },
  'YYYY-MM-DD': { year: 'numeric', month: '2-digit', day: '2-digit' },
};

const dateFormatLocale: Record<string, string> = {
  'MM/DD/YYYY': 'en-US',
  'DD/MM/YYYY': 'en-GB',
  'YYYY-MM-DD': 'sv-SE',  // Swedish locale gives YYYY-MM-DD naturally
};

function loadPreferences(): UserPreferences {
  try {
    const stored = localStorage.getItem(PREFERENCES_KEY);
    if (stored) {
      return { ...defaultPreferences, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.error('Failed to load preferences:', e);
  }
  return { ...defaultPreferences };
}

function savePreferences(prefs: UserPreferences): void {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs));
  } catch (e) {
    console.error('Failed to save preferences:', e);
  }
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined);

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(loadPreferences);

  const updatePreference = useCallback(<K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K]
  ) => {
    setPreferences((prev) => {
      const updated = { ...prev, [key]: value };
      savePreferences(updated);
      return updated;
    });
  }, []);

  const updatePreferences = useCallback((updates: Partial<UserPreferences>) => {
    setPreferences((prev) => {
      const updated = { ...prev, ...updates };
      savePreferences(updated);
      return updated;
    });
  }, []);

  const formatCurrency = useCallback((amount: number): string => {
    const locale = currencyLocaleMap[preferences.currency] || 'en-US';
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: preferences.currency,
        minimumFractionDigits: preferences.currency === 'JPY' || preferences.currency === 'KRW' ? 0 : 2,
        maximumFractionDigits: preferences.currency === 'JPY' || preferences.currency === 'KRW' ? 0 : 2,
      }).format(amount);
    } catch {
      // Fallback if currency code is invalid
      return `${getCurrencySymbolStatic(preferences.currency)}${amount.toFixed(2)}`;
    }
  }, [preferences.currency]);

  const formatDate = useCallback((dateString: string): string => {
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return dateString;
      
      const locale = dateFormatLocale[preferences.dateFormat] || 'en-US';
      const options = dateFormatOptions[preferences.dateFormat] || dateFormatOptions['MM/DD/YYYY'];
      
      return new Intl.DateTimeFormat(locale, options).format(date);
    } catch {
      return dateString;
    }
  }, [preferences.dateFormat]);

  const getCurrencySymbol = useCallback((): string => {
    return getCurrencySymbolStatic(preferences.currency);
  }, [preferences.currency]);

  return (
    <PreferencesContext.Provider value={{
      preferences,
      updatePreference,
      updatePreferences,
      formatCurrency,
      formatDate,
      getCurrencySymbol,
    }}>
      {children}
    </PreferencesContext.Provider>
  );
}

function getCurrencySymbolStatic(currency: string): string {
  return currencySymbolMap[currency] || currency;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (context === undefined) {
    throw new Error('usePreferences must be used within a PreferencesProvider');
  }
  return context;
}
