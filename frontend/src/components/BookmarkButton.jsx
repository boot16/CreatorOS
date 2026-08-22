import React from 'react';
import { Bookmark, BookmarkCheck } from 'lucide-react';
import { useShortlist } from '../lib/shortlist';

export default function BookmarkButton({ oppId, size = 18 }) {
  const { isSaved, toggle } = useShortlist();
  const saved = isSaved(oppId);
  return (
    <button
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggle(oppId); }}
      data-testid={`bookmark-${oppId}`}
      className="p-2 rounded-full transition-colors"
      style={{
        color: saved ? '#C4B5FD' : '#71717A',
        background: saved ? 'rgba(138,43,226,0.14)' : 'transparent',
      }}
      title={saved ? 'Saved to shortlist' : 'Save to shortlist'}
    >
      {saved ? <BookmarkCheck size={size} /> : <Bookmark size={size} />}
    </button>
  );
}
