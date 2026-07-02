import { UserPlus } from "lucide-react";
import RegisterForm from "./RegisterForm";
import { PageHeader } from "../_components/ui";

export default function RegisterPage() {
  return (
    <div className="max-w-xl mx-auto space-y-6">
      <PageHeader
        title="Create your patient profile"
        subtitle="You'll get a patient ID you can use to book appointments."
        icon={UserPlus}
      />
      <RegisterForm />
    </div>
  );
}
