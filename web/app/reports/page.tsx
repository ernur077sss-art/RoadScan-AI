import { Suspense } from "react";
import { ReportList } from "@/components/report-list";
export default function Page() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <ReportList />
    </Suspense>
  );
}
