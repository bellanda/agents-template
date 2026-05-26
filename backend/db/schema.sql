\restrict dbmate

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


--
-- Name: agent_message_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_message_usage (
    id integer NOT NULL,
    thread_id character varying(128) NOT NULL,
    message_id character varying(64) NOT NULL,
    user_id character varying(255),
    client_id character varying(255),
    agent_id character varying(255) NOT NULL,
    provider character varying(64) NOT NULL,
    model_id character varying(255) NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    cached_input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    reasoning_tokens integer DEFAULT 0 NOT NULL,
    total_tokens integer DEFAULT 0 NOT NULL,
    cost_usd numeric(12,6) DEFAULT 0 NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: agent_message_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_message_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_message_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_message_usage_id_seq OWNED BY public.agent_message_usage.id;


--
-- Name: chat_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_history (
    thread_id character varying(128) NOT NULL,
    user_id character varying(255) NOT NULL,
    client_id character varying(255),
    agent_id character varying(255) NOT NULL,
    messages jsonb DEFAULT '[]'::jsonb NOT NULL,
    preview text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: checkpoint_blobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checkpoint_blobs (
    thread_id character varying NOT NULL,
    checkpoint_ns character varying DEFAULT ''::character varying NOT NULL,
    channel character varying NOT NULL,
    version character varying NOT NULL,
    type character varying NOT NULL,
    blob bytea
);


--
-- Name: checkpoint_writes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checkpoint_writes (
    thread_id character varying NOT NULL,
    checkpoint_ns character varying DEFAULT ''::character varying NOT NULL,
    checkpoint_id character varying NOT NULL,
    task_id character varying NOT NULL,
    task_path character varying DEFAULT ''::character varying NOT NULL,
    idx integer NOT NULL,
    channel character varying NOT NULL,
    type character varying,
    blob bytea
);


--
-- Name: checkpoints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checkpoints (
    thread_id character varying NOT NULL,
    checkpoint_ns character varying DEFAULT ''::character varying NOT NULL,
    checkpoint_id character varying NOT NULL,
    parent_checkpoint_id character varying,
    type character varying,
    checkpoint jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_uploads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_uploads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_user_id character varying(255) NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    kind text NOT NULL,
    url text NOT NULL,
    filename text NOT NULL,
    mime_type text,
    size_bytes integer,
    width integer,
    height integer,
    visibility text DEFAULT 'public'::text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_user_uploads_kind CHECK ((kind = ANY (ARRAY['logo'::text, 'banner'::text, 'avatar'::text, 'photo'::text, 'gallery_image'::text, 'document'::text, 'attachment'::text, 'whatsapp_media'::text, 'export'::text, 'other'::text]))),
    CONSTRAINT ck_user_uploads_visibility CHECK ((visibility = ANY (ARRAY['public'::text, 'tenant'::text, 'private'::text])))
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: agent_message_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_message_usage ALTER COLUMN id SET DEFAULT nextval('public.agent_message_usage_id_seq'::regclass);


--
-- Name: agent_message_usage agent_message_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_message_usage
    ADD CONSTRAINT agent_message_usage_pkey PRIMARY KEY (id);


--
-- Name: chat_history chat_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_history
    ADD CONSTRAINT chat_history_pkey PRIMARY KEY (thread_id);


--
-- Name: checkpoint_blobs checkpoint_blobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkpoint_blobs
    ADD CONSTRAINT checkpoint_blobs_pkey PRIMARY KEY (thread_id, checkpoint_ns, channel, version);


--
-- Name: checkpoint_writes checkpoint_writes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkpoint_writes
    ADD CONSTRAINT checkpoint_writes_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx);


--
-- Name: checkpoints checkpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkpoints
    ADD CONSTRAINT checkpoints_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id);


--
-- Name: user_uploads user_uploads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_uploads
    ADD CONSTRAINT user_uploads_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: ix_agent_message_usage_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_message_usage_client_id ON public.agent_message_usage USING btree (client_id);


--
-- Name: ix_agent_message_usage_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_message_usage_created_at ON public.agent_message_usage USING btree (created_at);


--
-- Name: ix_agent_message_usage_thread_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_message_usage_thread_id ON public.agent_message_usage USING btree (thread_id);


--
-- Name: ix_chat_history_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_history_client_id ON public.chat_history USING btree (client_id);


--
-- Name: ix_chat_history_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_history_user_id ON public.chat_history USING btree (user_id);


--
-- Name: ix_user_uploads_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_uploads_entity ON public.user_uploads USING btree (entity_type, entity_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_user_uploads_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_uploads_kind ON public.user_uploads USING btree (kind) WHERE (deleted_at IS NULL);


--
-- Name: ix_user_uploads_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_uploads_owner_user_id ON public.user_uploads USING btree (owner_user_id);


--
-- Name: chat_history update_chat_history_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_chat_history_updated_at BEFORE UPDATE ON public.chat_history FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: user_uploads update_user_uploads_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_user_uploads_updated_at BEFORE UPDATE ON public.user_uploads FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION public.update_updated_at_column();


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20260427000000');
