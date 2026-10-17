import { UserRound } from "lucide-react";
export function DoctorAvatar({
  gender,
  avatar = false,
}: {
  gender: "male" | "female" | null;
  avatar?: boolean;
}) {
  return (
    <div className={avatar ? "doctor-avatar" : "greeting-art"}>
      {gender ? (
        <img
          src={`/mobile/welcome-${gender}.png`}
          alt={gender === "male" ? "Bác sĩ nam" : "Bác sĩ nữ"}
        />
      ) : (
        <UserRound
          aria-label="Chưa chọn hình đại diện"
          size={avatar ? 48 : 56}
        />
      )}
    </div>
  );
}
