"use client";

import { createContext, useContext, useState } from "react";

/**
 * The home page's second half, folded on a phone.
 *
 * On a desk the page is a spread: the read, where strength sits, the week and
 * the screens are all in view within a scroll or two. On a phone the same
 * sections stack into a single column about twelve screens long, and the
 * parts a reader comes back for every day (the read, what is dated, the
 * screens, their own list, the news) sit behind three reference charts that
 * change slowly. So at phone width those three fold behind one button, placed
 * after the news. Nothing is removed and nothing changes on a wider screen.
 *
 * The fold is a style rule, not a render decision: the sections are in the
 * page either way and the stylesheet hides them under 700px until the button
 * is pressed. That keeps the server's markup and the browser's identical, so
 * there is no flash on load, and a reader without scripting still gets the
 * whole page on any screen wide enough to want it.
 */
const FoldContext = createContext<{ open: boolean; toggle: () => void }>({
  open: false, toggle: () => {},
});

export function HomeFoldProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <FoldContext.Provider value={{ open, toggle: () => setOpen((was) => !was) }}>
      {children}
    </FoldContext.Provider>
  );
}

/** A section that folds away on a phone. `as` keeps the element it replaces. */
export function HomeFolded({
  children, className, style, as: Tag = "section",
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  as?: "section" | "div";
}) {
  const { open } = useContext(FoldContext);
  return (
    <Tag className={`phone-fold${className ? ` ${className}` : ""}`} style={style}
         data-phone-open={open ? "true" : "false"}>
      {children}
    </Tag>
  );
}

/** The button that opens the fold. Hidden wherever nothing is folded. */
export function HomeFoldButton({ what }: { what: string }) {
  const { open, toggle } = useContext(FoldContext);
  return (
    <div className="phone-fold-button">
      <button type="button" className="control" onClick={toggle} aria-expanded={open}>
        <span className="phone-fold-label">
          {open ? "Less from tonight" : "More from tonight"}
          <span aria-hidden>{open ? " −" : " +"}</span>
        </span>
        <span className="caption dim">{open ? "Fold these away again" : what}</span>
      </button>
    </div>
  );
}
