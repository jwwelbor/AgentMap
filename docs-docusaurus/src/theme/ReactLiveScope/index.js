import React from 'react';

// Basic components for documentation examples
export default {
  React,
  
  // Simple alert component for docs
  Alert: ({ children, type = 'info', style = {} }) => {
    const colors = {
      info: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af' },
      success: { bg: '#f0fdf4', border: '#bbf7d0', text: '#15803d' },
      warning: { bg: '#fffbeb', border: '#fed7aa', text: '#d97706' },
      error: { bg: '#fef2f2', border: '#fecaca', text: '#dc2626' }
    };
    const color = colors[type] || colors.info;
    
    return (
      <div style={{
        padding: '0.75rem',
        backgroundColor: color.bg,
        border: `1px solid ${color.border}`,
        borderRadius: '6px',
        color: color.text,
        fontSize: '0.9rem',
        ...style
      }}>
        {children}
      </div>
    );
  },

  // Simple button component
  Button: ({ children, onClick, disabled, style = {} }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '0.5rem 1rem',
        backgroundColor: disabled ? '#9ca3af' : '#3b82f6',
        color: 'white',
        border: 'none',
        borderRadius: '6px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: '0.9rem',
        ...style
      }}
    >
      {children}
    </button>
  ),

  // Simple card component
  Card: ({ children, title, style = {} }) => (
    <div style={{
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      padding: '1rem',
      backgroundColor: '#f8f9fa',
      ...style
    }}>
      {title && <h4 style={{ margin: '0 0 0.5rem 0', color: '#2d3748' }}>{title}</h4>}
      {children}
    </div>
  )
};
