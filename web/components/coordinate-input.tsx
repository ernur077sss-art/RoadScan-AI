"use client";
import { useEffect, useState } from "react";
// Keep the edit buffer so a trailing decimal separator or minus sign survives typing.
export function CoordinateInput({
  id,
  value,
  onChange,
}: {
  id: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => {
    if (value == null) setText("");
    else if (Number.isFinite(value))
      setText((previous) =>
        Number(previous.replace(",", ".")) === value ? previous : String(value),
      );
  }, [value]);
  return (
    <input
      id={id}
      type="text"
      inputMode="decimal"
      value={text}
      onChange={(event) => {
        const next = event.target.value;
        setText(next);
        onChange(next.trim() === "" ? null : Number(next.replace(",", ".")));
      }}
    />
  );
}
