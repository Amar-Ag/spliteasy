/** Names group members relative to the signed-in user ("You paid", "Bob owes you"). */
export interface People {
  currentUserId: string;
  /** "You" or the username — for the start of a sentence. */
  subject(userId: string): string;
  /** "you" or the username — for mid-sentence. */
  object(userId: string): string;
}
