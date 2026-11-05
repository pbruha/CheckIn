import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, isTeacher, useAuth } from './lib/auth';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { TeacherSession } from './pages/TeacherSession';
import { GroupStats } from './pages/GroupStats';
import { StudentDashboard } from './pages/StudentDashboard';
import { StudentCheckin } from './pages/StudentCheckin';

function RequireAuth({ children, teacherOnly = false }: { children: ReactNode; teacherOnly?: boolean }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="center muted">Načítání…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (teacherOnly && !isTeacher(user.role)) return <Navigate to="/student" replace />;
  return <>{children}</>;
}

function Home() {
  const { user } = useAuth();
  return <Navigate to={isTeacher(user?.role) ? '/teacher' : '/student'} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Home />
              </RequireAuth>
            }
          />
          <Route
            path="/teacher"
            element={
              <RequireAuth teacherOnly>
                <Layout title="Moje skupiny">
                  <TeacherDashboard />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/teacher/sessions/:id"
            element={
              <RequireAuth teacherOnly>
                <Layout title="Hodina">
                  <TeacherSession />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/teacher/groups/:id/stats"
            element={
              <RequireAuth teacherOnly>
                <Layout title="Statistiky">
                  <GroupStats />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/student"
            element={
              <RequireAuth>
                <Layout title="Moje docházka">
                  <StudentDashboard />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/student/checkin"
            element={
              <RequireAuth>
                <Layout title="Zapsat docházku">
                  <StudentCheckin />
                </Layout>
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
