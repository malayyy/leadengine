import React from 'react';

export function MetricSkeleton() {
  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 p-6 rounded-2xl shadow-xl animate-pulse">
      <div className="h-3 w-20 bg-white/10 rounded mb-3" />
      <div className="h-8 w-16 bg-white/10 rounded" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }) {
  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-pulse">
      <div className="p-5 border-b border-white/10 bg-black/20">
        <div className="h-4 w-32 bg-white/10 rounded" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 p-4 border-b border-white/5">
          {Array.from({ length: cols }).map((_, j) => (
            <div key={j} className="h-3 bg-white/10 rounded flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl overflow-hidden shadow-2xl p-6 animate-pulse">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-white/10 rounded-lg" />
        <div className="h-4 w-40 bg-white/10 rounded" />
      </div>
      <div className="h-48 bg-white/5 rounded-lg" />
    </div>
  );
}
