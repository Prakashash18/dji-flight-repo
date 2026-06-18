-- Enable PostGIS extension for spatial queries (mapping coordinates & zones)
create extension if not exists postgis;

-- 1. Profiles Table (Volunteers & Coordinators)
create table public.profiles (
    id uuid references auth.users on delete cascade primary key,
    name text not null,
    role text not null check (role in ('coordinator', 'volunteer')),
    preferred_language text not null default 'en',
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

comment on table public.profiles is 'Stores volunteer and coordinator profile metadata linked to Auth users.';

-- 2. Litter Pins Table (Detections)
create table public.litter_pins (
    id uuid default gen_random_uuid() primary key,
    latitude double precision not null,
    longitude double precision not null,
    location geometry(Point, 4326), -- PostGIS Point geometry
    image_url text,                 -- Supabase storage url or external link
    confidence double precision not null default 0.0,
    status text not null default 'detected' check (status in ('detected', 'cleaning', 'cleaned')),
    detected_at timestamp with time zone default timezone('utc'::text, now()) not null,
    cleaned_at timestamp with time zone,
    cleaned_by uuid references public.profiles(id) on delete set null
);

create index litter_pins_location_idx on public.litter_pins using gist (location);
comment on table public.litter_pins is 'Pin points representing litter detected by the processing station YOLOv8.';

-- Trigger to automatically calculate PostGIS Point geometry from latitude & longitude
create or replace function public.update_litter_pin_geom()
returns trigger as $$
begin
    new.location := st_setsrid(st_makepoint(new.longitude, new.latitude), 4326);
    return new;
end;
$$ language plpgsql;

create trigger tr_litter_pins_geom
    before insert or update of latitude, longitude on public.litter_pins
    for each row execute function public.update_litter_pin_geom();

-- 3. Cleanup Zones Table (Polygons assigned to volunteers)
create table public.cleanup_zones (
    id uuid default gen_random_uuid() primary key,
    name text not null,
    boundary geometry(Polygon, 4326), -- PostGIS Polygon geometry
    boundary_geojson jsonb not null,  -- Raw GeoJSON backup for frontend/mobile ease
    assigned_to uuid references public.profiles(id) on delete set null,
    status text not null default 'pending' check (status in ('pending', 'in_progress', 'completed')),
    created_by uuid references public.profiles(id) on delete set null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

create index cleanup_zones_boundary_idx on public.cleanup_zones using gist (boundary);
comment on table public.cleanup_zones is 'Coastal zones mapped for cleanup campaigns assigned to volunteers.';

-- Trigger to automatically sync PostGIS boundary from boundary_geojson when updated
create or replace function public.update_cleanup_zone_geom()
returns trigger as $$
begin
    new.boundary := st_geomfromgeojson(new.boundary_geojson::text);
    return new;
exception when others then
    -- Fallback/graceful fail if invalid GeoJSON
    return new;
end;
$$ language plpgsql;

create trigger tr_cleanup_zones_geom
    before insert or update of boundary_geojson on public.cleanup_zones
    for each row execute function public.update_cleanup_zone_geom();

-- 4. Alerts Table (Multilingual broadcasts via SEA-LION API)
create table public.alerts (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    message text not null,
    translations jsonb not null default '{}'::jsonb, -- e.g. {"th": "...", "id": "...", "tl": "..."}
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

comment on table public.alerts is 'Multilingual broadcasts sent by coordinators, translated using SEA-LION.';

---
--- ROW LEVEL SECURITY (RLS) POLICIES
---
alter table public.profiles enable row level security;
alter table public.litter_pins enable row level security;
alter table public.cleanup_zones enable row level security;
alter table public.alerts enable row level security;

-- Profiles Policies
create policy "Allow public reading of profiles" on public.profiles
    for select using (true);

create policy "Users can update their own profiles" on public.profiles
    for update using (auth.uid() = id);

-- Litter Pins Policies
create policy "Allow public reading of pins" on public.litter_pins
    for select using (true);

create policy "Allow inserting of pins by anyone (or processing station service role)" on public.litter_pins
    for insert with check (true);

create policy "Allow updating pin status by authenticated users" on public.litter_pins
    for update using (auth.role() = 'authenticated');

-- Cleanup Zones Policies
create policy "Allow reading of cleanup zones" on public.cleanup_zones
    for select using (true);

create policy "Coordinators can manage zones" on public.cleanup_zones
    for all using (
        exists (
            select 1 from public.profiles
            where id = auth.uid() and role = 'coordinator'
        )
    );

create policy "Volunteers can update zones assigned to them" on public.cleanup_zones
    for update using (
        assigned_to = auth.uid()
    );

-- Alerts Policies
create policy "Allow reading of alerts by everyone" on public.alerts
    for select using (true);

create policy "Only coordinators can create alerts" on public.alerts
    for insert with check (
        exists (
            select 1 from public.profiles
            where id = auth.uid() and role = 'coordinator'
        )
    );

---
--- REAL-TIME SETUP
---
-- Enable Realtime for Litter Pins and Cleanup Zones
begin;
  drop publication if exists supabase_realtime;
  create publication supabase_realtime;
commit;

alter publication supabase_realtime add table public.litter_pins;
alter publication supabase_realtime add table public.cleanup_zones;
alter publication supabase_realtime add table public.alerts;

---
--- MIGRATION: MISSIONS & ONBOARDING SUPPORT
---

-- 1. Create Missions Table
create table if not exists public.missions (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    description text,
    mission_date timestamp with time zone default timezone('utc'::text, now()) not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS for missions
alter table public.missions enable row level security;
create policy "Allow reading of missions by everyone" on public.missions for select using (true);
create policy "Allow inserting of missions by everyone" on public.missions for insert with check (true);
create policy "Allow updating of missions by everyone" on public.missions for update using (true);

-- 2. Add mission_id reference to litter_pins
alter table public.litter_pins add column if not exists mission_id uuid references public.missions(id) on delete cascade;

-- 3. Modify Profiles table to simplify user onboarding
-- Drop foreign key constraint pointing to auth.users so we can insert mock/volunteer profiles directly from client app
alter table public.profiles drop constraint if exists profiles_id_fkey;
alter table public.profiles alter column id set default gen_random_uuid();
create policy "Allow inserting of profiles by everyone" on public.profiles for insert with check (true);

-- 4. Enable Realtime for Missions and Profiles
alter publication supabase_realtime add table public.missions;
alter publication supabase_realtime add table public.profiles;
