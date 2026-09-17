import { motion } from "framer-motion";
import { DocBreadcrumb } from "./DocBreadcrumb";
import { DocSection } from "./DocSection";
import { documentationContent } from "@/data/documentation";

export function DocContent() {
  return (
    <main className="flex-1 min-w-0 px-6 lg:px-12 py-10">
      <div className="max-w-3xl">
        <DocBreadcrumb items={documentationContent.breadcrumb} />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            {documentationContent.title}
          </h1>
          <p className="text-lg text-muted-foreground mb-12">
            {documentationContent.description}
          </p>
        </motion.div>

        <div className="space-y-12">
          <DocSection id="introduction" title="Introduction">
            <p>
              Welcome to the Sotlas Help Center. This guide will walk you through the essential steps to set up your account and get started with the platform. Whether you're new to Sotlas or migrating from another tool, this documentation covers everything you need.
            </p>
            <p>
              Before you begin, make sure you have your email address ready and access to your organization's workspace settings if you're joining an existing team.
            </p>
          </DocSection>

          <DocSection id="creating-your-account" title="Creating Your Account">
            <p>
              Setting up your Sotlas account takes just a few minutes. Follow the steps below to create your account and join or create a workspace for your team.
            </p>
          </DocSection>

          <DocSection id="sign-up-process" title="Sign-up Process" level="h3">
            <ol className="list-decimal list-inside space-y-2 ml-2">
              <li>Navigate to the Sotlas sign-up page and click "Create Account".</li>
              <li>Enter your email address and create a strong password.</li>
              <li>Choose whether to create a new workspace or join an existing one.</li>
              <li>Complete the captcha verification to confirm you're human.</li>
              <li>Click "Continue" to proceed to email verification.</li>
            </ol>
          </DocSection>

          <DocSection id="account-verification" title="Account Verification" level="h3">
            <p>
              After signing up, you'll receive a verification email. Click the link in the email to verify your account. If you don't see the email, check your spam folder or request a new verification link from the login page.
            </p>
            <p>
              Verification links expire after 24 hours. If your link has expired, you can request a new one by clicking "Resend verification email" on the sign-in page.
            </p>
          </DocSection>

          <DocSection id="workspace-details" title="Workspace & Project Details">
            <p>
              Your workspace is where all your projects, team members, and settings live. Each workspace can contain multiple projects and has its own billing and permissions structure.
            </p>
          </DocSection>

          <DocSection id="adding-a-workspace" title="Adding a Workspace" level="h3">
            <ol className="list-decimal list-inside space-y-2 ml-2">
              <li>From the dashboard, click "Create Workspace" in the sidebar.</li>
              <li>Enter a name for your workspace (e.g., your company name).</li>
              <li>Choose the primary region for data storage and processing.</li>
              <li>Invite team members by email or share the workspace invite link.</li>
              <li>Configure initial project settings and permissions.</li>
            </ol>
          </DocSection>

          <DocSection id="supported-regions" title="Supported Regions" level="h3">
            <p>
              Sotlas supports data residency in multiple regions to help you comply with local regulations. Currently available regions include:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2 mt-4">
              <li>United States (US-East, US-West)</li>
              <li>European Union (EU-Central, EU-West)</li>
              <li>Asia Pacific (APAC-Singapore, APAC-Sydney)</li>
              <li>United Kingdom (UK-London)</li>
            </ul>
          </DocSection>

          <DocSection id="configuration" title="Configuration">
            <p>
              Once your workspace is created, you can customize it to fit your team's workflow. This includes setting up integrations, configuring notifications, and establishing team roles and permissions.
            </p>
            <p>
              Most settings can be adjusted later, so don't worry about getting everything perfect on the first try. Focus on the essentials and refine your setup as you learn what works best for your team.
            </p>
          </DocSection>

          <DocSection id="security-setup" title="Security Setup">
            <p>
              Protecting your account and data is crucial. Sotlas offers multiple layers of security to keep your information safe. We recommend enabling all available security features for maximum protection.
            </p>
          </DocSection>

          <DocSection id="two-factor-auth" title="Two-Factor Authentication" level="h3">
            <ol className="list-decimal list-inside space-y-2 ml-2">
              <li>Navigate to Settings → Security → Two-Factor Authentication.</li>
              <li>Choose your preferred method: authenticator app or SMS.</li>
              <li>Scan the QR code with your authenticator app or enter your phone number.</li>
              <li>Enter the verification code to confirm setup.</li>
              <li>Save your backup codes in a secure location.</li>
            </ol>
          </DocSection>

          <DocSection id="recovery-options" title="Setting Up Recovery Options" level="h3">
            <p>
              Recovery options ensure you can regain access to your account if you lose your primary authentication method. We strongly recommend setting up at least two recovery methods.
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2 mt-4">
              <li>Backup email address for password recovery</li>
              <li>Phone number for SMS verification</li>
              <li>Recovery codes stored securely offline</li>
              <li>Trusted devices for seamless sign-in</li>
            </ul>
          </DocSection>

          <DocSection id="notifications" title="Notifications & Preferences">
            <p>
              Customize how and when you receive notifications from Sotlas. You can configure email notifications, in-app alerts, and mobile push notifications separately.
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2 mt-4">
              <li>Email digests: daily, weekly, or real-time notifications</li>
              <li>In-app notifications for mentions and assignments</li>
              <li>Mobile push notifications for urgent updates</li>
              <li>Quiet hours to pause notifications during specific times</li>
            </ul>
          </DocSection>

          <DocSection id="reviewing-setup" title="Reviewing Your Setup">
            <p>
              Before you start using Sotlas in production, take a moment to review your setup and ensure everything is configured correctly. This will help you avoid issues later.
            </p>
          </DocSection>

          <DocSection id="checklist" title="Checklist for a Complete Account" level="h3">
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>Email address verified and confirmed</li>
              <li>Two-factor authentication enabled</li>
              <li>Recovery options configured and tested</li>
              <li>Workspace created with appropriate region</li>
              <li>Team members invited with correct permissions</li>
              <li>Notification preferences customized</li>
              <li>Profile information completed</li>
            </ul>
          </DocSection>

          <DocSection id="testing-sandbox" title="Testing in Sandbox Mode" level="h3">
            <p>
              Before going live, use Sandbox Mode to test your integrations and workflows without affecting production data. Sandbox mode provides a safe environment to experiment and learn.
            </p>
            <ol className="list-decimal list-inside space-y-2 ml-2 mt-4">
              <li>Toggle "Sandbox Mode" in the top navigation bar.</li>
              <li>Create test projects and data without any risk.</li>
              <li>Test integrations with third-party services.</li>
              <li>Verify workflows and automations work as expected.</li>
              <li>Switch back to production when you're ready.</li>
            </ol>
          </DocSection>
        </div>
      </div>
    </main>
  );
}
