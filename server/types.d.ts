// 14:0
import "express-session";

declare module "express-session" {
  interface SessionData {
    userId?: string;
    userEmail?: string;
    userRole?: string;
    pendingResetUserId?: string;
    pendingResetExpiry?: number;
    pendingResetIsDecoy?: boolean;
    resetFailureCount?: number;
    resetVerifiedUserId?: string;
    resetToken?: string;
    resetTokenHash?: string;
    resetTokenExpiry?: number;
    resetIsHoneypot?: boolean;
  }
}

export {};
// 14:0
