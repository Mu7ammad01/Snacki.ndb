const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const Plus = () => (<svg {...base} strokeWidth={2.6}><path d="M12 5v14M5 12h14" /></svg>);
export const Minus = () => (<svg {...base} strokeWidth={2.6}><path d="M5 12h14" /></svg>);
export const Leaf = () => (<svg {...base} strokeWidth={2}><path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z" /><path d="M5 19l7-7" /></svg>);
export const Back = () => (<svg {...base} strokeWidth={2.4} className="flip"><path d="M15 18l-6-6 6-6" /></svg>);
export const Close = () => (<svg {...base} strokeWidth={2.4}><path d="M6 6l12 12M18 6L6 18" /></svg>);
export const Wa = () => (
  <svg {...base} strokeWidth={1.8}>
    <path d="M20.5 11.6a8.4 8.4 0 0 1-12.4 7.4L3.5 20.5l1.6-4.4A8.4 8.4 0 1 1 20.5 11.6z" />
    <path d="M9 8.6c0 3.2 2.9 6.3 6.3 6.4l1.1-1.4-1.9-1-.9.8c-1-.4-2.4-1.8-2.9-2.9l.8-.9-.9-1.9L9 8.6z" strokeWidth={1.6} />
  </svg>
);
