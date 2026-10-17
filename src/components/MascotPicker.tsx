import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { updateWorkspace, useWorkspace } from "../lib/learnerWorkspace";
import { Sheet } from "./Sheet";
export const MASCOT_CHARACTERS = [
  ["robot", "Robot"],
  ["cat", "Mèo"],
  ["owl", "Cú mèo"],
  ["panda", "Gấu trúc"],
  ["scientist", "Nhà khoa học"],
  ["fox", "Cáo"],
] as const;

export function MascotPickerSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const w = useWorkspace();
  return (
    <Sheet open={open} onClose={onClose} title="Chọn linh vật AI">
      <fieldset className="mascot-picker">
        <legend>Linh vật của bạn</legend>
        <div>
          {MASCOT_CHARACTERS.map(([id, label]) => (
            <button
              type="button"
              key={id}
              aria-pressed={w.mascot === id}
              onClick={() => updateWorkspace((prev) => ({ ...prev, mascot: id }))}
            >
              <span
                aria-hidden="true"
                style={{
                  backgroundImage: `url(/mobile/mascot-${id}-directions.png)`,
                }}
              />
              {label}
            </button>
          ))}
        </div>
        <p className="muted small">
          Lưu ngay trên thiết bị. Robot là lựa chọn mặc định.
        </p>
      </fieldset>
    </Sheet>
  );
}

export function MascotPicker() {
  const w = useWorkspace(),
    [open, setOpen] = useState(false);
  const name =
    MASCOT_CHARACTERS.find(([id]) => id === w.mascot)?.[1] ?? "Robot";
  return (
    <>
      <button
        className="mascot-setting"
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Đổi linh vật AI"
      >
        <span
          className="mascot-thumbnail"
          aria-hidden="true"
          style={{
            backgroundImage: `url(/mobile/mascot-${w.mascot}-directions.png)`,
          }}
        />
        <strong>Bạn đồng hành AI</strong>
        <span>{name}</span>
        <ChevronRight size={16} />
      </button>
      <MascotPickerSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
