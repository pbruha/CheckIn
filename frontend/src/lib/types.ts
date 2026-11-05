export type Lesson = {
  id: number;
  group_id: number;
  starts_at: string;
  ends_at: string;
  status: 'ready' | 'running' | 'closed';
};

export type MyGroup = { id: number; course_id: number; name: string; role: 'teacher' | 'student' };

export type MyAttendanceItem = {
  session_id: number;
  group_id: number;
  group_name: string;
  starts_at: string;
  ends_at: string;
  session_status: Lesson['status'];
  status: string | null;
  recorded_at: string | null;
};

export type MyAttendance = {
  absences: number;
  absence_limit: number;
  remaining: number;
  items: MyAttendanceItem[];
};

export type LiveStudent = {
  user_id: number;
  name: string;
  email: string;
  status: string;
  method: string | null;
  recorded_at: string | null;
};

export type LiveAttendance = {
  session: Lesson;
  counts: Record<string, number>;
  students: LiveStudent[];
};

export type QrInfo = {
  qr_token: string;
  qr_expires_in: number;
  code: string;
  code_expires_in: number;
};

export type GroupStats = {
  closed_sessions: number;
  absence_limit: number;
  students: {
    user_id: number;
    name: string;
    email: string;
    present: number;
    late: number;
    excused: number;
    absent: number;
    attendance_rate: number | null;
    over_limit: boolean;
  }[];
  sessions: { session_id: number; starts_at: string; present: number; enrolled: number }[];
};

export type Excuse = {
  id: number;
  session_id: number;
  status: 'pending' | 'approved' | 'rejected';
  text: string;
  has_attachment: boolean;
  attachment_name: string | null;
  created_at: string;
  decided_at: string | null;
  decision_note: string | null;
};

export type ManagedExcuse = Excuse & {
  student: { id: number; name: string; email: string };
  session: Lesson;
  group: { id: number; name: string };
};

export type Notification = {
  type: 'absence_limit' | 'excuse_decision' | 'pending_excuses';
  level: 'info' | 'warning' | 'danger';
  text: string;
  group?: string;
  note?: string | null;
  count?: number;
};
