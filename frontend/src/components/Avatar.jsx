import React from 'react';

export default function Avatar({ gradient = ['#8A2BE2','#4C1D95'], initials = '?', size = 44, testId }) {
  return (
    <div
      className="flex items-center justify-center rounded-full font-display font-semibold text-white shrink-0"
      style={{
        width: size, height: size,
        background: `linear-gradient(135deg, ${gradient[0]}, ${gradient[1]})`,
        fontSize: size * 0.38,
        boxShadow: '0 4px 20px -8px rgba(0,0,0,0.6)',
      }}
      data-testid={testId}
    >
      {initials}
    </div>
  );
}
