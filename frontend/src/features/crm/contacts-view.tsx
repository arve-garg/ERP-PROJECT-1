import { Edit2, Mail, Phone, Plus, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import { Button } from "../../components/ui/button";
import type { Contact } from "./types";

interface ContactsViewProps {
  contacts: Contact[];
  isLoading: boolean;
  onAddContact: () => void;
  onEditContact: (contact: Contact) => void;
}

export function ContactsView({
  contacts,
  isLoading,
  onAddContact,
  onEditContact,
}: ContactsViewProps) {
  const [search, setSearch] = useState("");

  const filtered = contacts.filter((c) => {
    const q = search.toLowerCase();
    return (
      c.first_name.toLowerCase().includes(q) ||
      c.last_name.toLowerCase().includes(q) ||
      c.organization.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.phone.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-72">
          <Search size={15} className="absolute left-2.5 top-2.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search contacts by name, company, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded border border-border bg-surface pl-8 pr-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <Button onClick={onAddContact} size="sm" className="w-full sm:w-auto">
          <Plus size={14} className="mr-1.5" /> Add Contact
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border bg-muted/40 text-muted-foreground uppercase font-medium">
              <tr>
                <th className="px-4 py-3">Name & Title</th>
                <th className="px-4 py-3">Organization</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Notes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground animate-pulse">
                    Loading contacts...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No contacts found.
                  </td>
                </tr>
              ) : (
                filtered.map((contact) => (
                  <tr key={contact.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground flex items-center gap-1.5">
                        <UserCheck size={14} className="text-muted-foreground" />
                        {contact.full_name}
                      </div>
                      {contact.title && (
                        <div className="text-[11px] text-muted-foreground">{contact.title}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-foreground font-medium">
                      {contact.organization || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {contact.email ? (
                        <a
                          href={`mailto:${contact.email}`}
                          className="flex items-center gap-1 text-primary hover:underline"
                        >
                          <Mail size={12} /> {contact.email}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {contact.phone ? (
                        <span className="flex items-center gap-1">
                          <Phone size={12} /> {contact.phone}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground max-w-xs truncate">
                      {contact.notes || "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onEditContact(contact)}
                        className="h-7 w-7 p-0"
                        title="Edit contact"
                      >
                        <Edit2 size={13} />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
