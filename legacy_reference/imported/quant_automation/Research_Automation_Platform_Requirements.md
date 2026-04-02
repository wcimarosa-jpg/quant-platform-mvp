# Research Automation Platform - Requirements Document

**Version:** 1.0  
**Date:** November 5, 2025  
**Purpose:** Full automation of market research workflow from questionnaire generation through advanced analytics

---

## Executive Summary

This platform automates the complete market research workflow, eliminating manual data entry and streamlining analysis. Users generate questionnaires via AI, export directly to survey platforms, collect responses, populate data tables automatically, and run advanced statistical analyses—all within a single interface.

---

## End User Journey Summary

### Primary User Flow

1. **Questionnaire Development**
   - User inputs research objectives and parameters
   - AI generates initial questionnaire with appropriate question types and logic
   - System assigns question-level IDs based on analytics requirements
   - User reviews and iterates on questionnaire structure

2. **Survey Programming**
   - User selects target survey platform (Qualtrics, Decipher, Alchemer, Confirmit)
   - System translates questionnaire to platform-specific format
   - Direct API export to survey platform
   - Automated testing checklist generated
   - User conducts platform-native testing

3. **Table Planning**
   - System generates blank data tables based on questionnaire structure
   - Question IDs map to table columns
   - Cross-tabulation structure defined
   - Export table shells for stakeholder review

4. **Data Collection & Population**
   - User exports raw data from survey platform
   - System validates data structure against questionnaire
   - Automated population of data tables with response data
   - Data cleaning and validation logs generated

5. **Analytics Execution**
   - User selects analytics based on question types/IDs
   - System runs appropriate statistical analyses:
     - K-means clustering for attitudinal segmentation
     - VarClus for behavioral groupings
     - MaxDiff utility scores
     - TURF analysis
     - Significance testing across segments
   - Results exported in business-ready format

6. **Reporting**
   - Automated generation of findings documents
   - Visualization of key insights
   - Export to PowerPoint/PDF formats

---

## System Architecture Requirements

### Infrastructure

**Technology Stack:**
- Frontend: Streamlit (Python)
- Backend: Python 3.10+
- AI Engine: OpenAI API (GPT-4)
- Database: PostgreSQL or SQLite (for user sessions/projects)
- File Storage: Local file system or cloud storage (S3/Azure Blob)

**Concurrent User Support:**
- Support 10+ simultaneous users
- Session management via Streamlit's built-in session state
- User authentication system (username/password)
- Project isolation (each user's projects stored separately)
- Queue management for long-running analytics tasks

**API Integration Requirements:**
- OpenAI API for questionnaire generation
- Survey Platform APIs:
  - Qualtrics REST API v3
  - Decipher/Forsta XML API
  - Alchemer REST API
  - Confirmit SOAP/REST API
- Rate limiting and error handling for all external APIs

---

## Security Architecture & Infrastructure (Azure-Based)

### Overview

The platform will be deployed on Microsoft Azure, leveraging cloud-native services for security, scalability, and reliability. This architecture supports 10+ concurrent users with capability to scale to 50+ users without re-architecture.

---

### Computation Layer

**Primary Application Hosting:**

**Option 1: Azure Container Apps (Recommended)**
- **Purpose:** Host Streamlit application
- **Why:** Serverless container platform, auto-scales, cost-effective
- **Specs:** 
  - 2-4 vCPUs per instance
  - 4-8 GB RAM per instance
  - Auto-scale: 2-10 instances based on load
  - HTTP/HTTPS ingress with built-in load balancer
- **Cost Estimate:** $150-300/month for 10 concurrent users
- **Advantages:**
  - No server management
  - Automatic HTTPS
  - Built-in monitoring
  - Easy CI/CD integration

**Option 2: Azure App Service (Alternative)**
- **Purpose:** Host Streamlit as web app
- **Why:** Fully managed, simpler deployment
- **Specs:**
  - P1v3 tier (2 cores, 8 GB RAM)
  - Scale to P2v3 for heavier workloads
- **Cost Estimate:** $200-400/month
- **Advantages:**
  - One-click deployment
  - Built-in scaling
  - Easy custom domain setup

**Analytics Computation Engine:**

**Azure Batch (Recommended for Heavy Analytics)**
- **Purpose:** Run long-running analytics jobs (K-means on 10k+ respondents, VarClus, etc.)
- **Why:** Dedicated compute for batch processing, doesn't block web interface
- **Specs:**
  - Low-priority VMs for cost savings (Standard_D4s_v3: 4 cores, 16 GB RAM)
  - Pool of 2-5 VMs, auto-scale based on queue depth
- **Workflow:**
  1. User clicks "Run Analysis" in Streamlit
  2. Job submitted to Azure Batch queue
  3. Worker VM picks up job, runs Python analytics script
  4. Results written to Azure Blob Storage
  5. Streamlit polls for completion, displays results
- **Cost Estimate:** $50-150/month (low-priority VMs are 80% cheaper)

**Alternative: In-Process Analytics**
- For lighter workloads (<1000 respondents), run analytics directly in Streamlit container
- Pros: Simpler architecture
- Cons: May block UI during processing, limited to container resources

**Recommendation:** Start with in-process analytics, migrate to Azure Batch when users report slowness or dataset size increases.

---

### Data Storage Layer

**Database: Azure Database for PostgreSQL**
- **Purpose:** Store project metadata, user accounts, questionnaire versions, analytics runs
- **Tier:** Flexible Server - Burstable B2s (2 vCores, 4 GB RAM)
- **Storage:** 32-128 GB, auto-grow enabled
- **Backup:** Automated daily backups, 7-day retention
- **Cost Estimate:** $80-150/month
- **Schema:**
  - `users` (user_id, username, email, password_hash, role, created_at)
  - `projects` (project_id, name, owner_user_id, created_at, updated_at, status)
  - `questionnaires` (questionnaire_id, project_id, version, json_content, created_at)
  - `analytics_jobs` (job_id, project_id, analysis_type, status, created_at, completed_at, result_path)
  - `exports` (export_id, project_id, platform, survey_url, exported_at)
  - `audit_logs` (log_id, user_id, action, timestamp, ip_address)

**File Storage: Azure Blob Storage**
- **Purpose:** Store all project files (raw data, exports, reports, tables)
- **Tier:** Hot tier for active projects, Cool tier for archived projects
- **Structure:**
  ```
  Container: research-platform-data
    /projects/{project_id}/
      /questionnaires/
        - v1.0.json
      /data/
        - raw_data.csv
        - cleaned_data.csv
      /exports/
        - qualtrics_export.qsf
      /outputs/
        /tables/
          - crosstabs.xlsx
        /analytics/
          - kmeans_results.json
        /reports/
          - executive_report.pptx
  ```
- **Access:** Use Azure Storage SDKs (Python), SAS tokens for temporary download links
- **Lifecycle Management:** 
  - Move to Cool tier after 90 days of inactivity
  - Archive after 1 year
  - Delete after 3 years (configurable)
- **Cost Estimate:** $20-50/month for 100 GB, first 50 GB free
- **Redundancy:** Locally-redundant storage (LRS) for cost, or Zone-redundant (ZRS) for higher availability

---

### Security Layer

**1. Authentication & Identity Management**

**Azure Active Directory (Azure AD) - Recommended**
- **Implementation:** Integrate Azure AD for enterprise SSO
- **Benefits:**
  - Single sign-on (SSO) for users
  - Multi-factor authentication (MFA) enforced at tenant level
  - Conditional access policies (block access from untrusted locations)
  - Integration with existing corporate identity systems
- **User Roles:**
  - **Admin:** Full access, user management, system settings
  - **Analyst:** Create projects, run analytics, export data
  - **Viewer:** Read-only access to projects they're assigned to
- **Implementation in Streamlit:**
  - Use `msal` (Microsoft Authentication Library) Python package
  - OAuth 2.0 authentication flow
  - Store tokens in encrypted session state
- **Cost:** Free tier supports unlimited users for basic authentication

**Alternative: Custom Authentication (Not Recommended)**
- Username/password with bcrypt hashing
- Only use if Azure AD integration is blocked by IT policies
- Requires building password reset, MFA, session management

**2. Network Security**

**Azure Virtual Network (VNet)**
- Deploy all resources within private VNet
- Subnets:
  - **Web subnet:** Container Apps/App Service
  - **Data subnet:** PostgreSQL, Batch VMs
  - **Storage subnet:** Blob Storage (with private endpoint)

**Azure Firewall / Network Security Groups (NSGs)**
- **Inbound rules:**
  - Allow HTTPS (443) from internet to web app
  - Block all other inbound traffic
- **Outbound rules:**
  - Allow web app to connect to PostgreSQL (port 5432)
  - Allow web app to connect to Blob Storage (port 443)
  - Allow web app to call external APIs (OpenAI, Qualtrics, etc.)
  - Block all other outbound traffic
- **Private Endpoints:** 
  - PostgreSQL: No public IP, accessible only from VNet
  - Blob Storage: Optional private endpoint for enhanced security

**Azure DDoS Protection**
- Basic tier (free): Automatic protection against common DDoS attacks
- Standard tier ($3000/month): Advanced protection - only if required by compliance

**3. Data Encryption**

**Encryption at Rest:**
- **Azure Blob Storage:** 256-bit AES encryption (enabled by default)
- **Azure PostgreSQL:** TLS 1.2+ enforced, data encrypted with Microsoft-managed keys
- **Option for Customer-Managed Keys (CMK):**
  - Use Azure Key Vault to manage encryption keys
  - Provides audit trail of key usage
  - Required for certain compliance standards (HIPAA, SOC 2)

**Encryption in Transit:**
- **HTTPS only:** Enforce TLS 1.2+ for all web traffic
- **PostgreSQL connections:** SSL required for all database connections
- **Blob Storage:** All SDK calls use HTTPS

**4. Secrets Management**

**Azure Key Vault**
- **Purpose:** Store all sensitive credentials and API keys
- **Contents:**
  - OpenAI API key
  - Survey platform API credentials (Qualtrics, Decipher, etc.)
  - Database connection strings
  - JWT signing keys
- **Access Control:**
  - Managed identity for Container Apps (no credentials in code)
  - Audit logs for all secret retrievals
  - Automatic secret rotation (90-day policy)
- **Implementation:**
  ```python
  from azure.identity import DefaultAzureCredential
  from azure.keyvault.secrets import SecretClient
  
  credential = DefaultAzureCredential()
  client = SecretClient(vault_url="https://research-platform-kv.vault.azure.net/", credential=credential)
  
  openai_key = client.get_secret("openai-api-key").value
  ```
- **Cost:** $0.03 per 10,000 operations, ~$5/month

**5. Access Control & Authorization**

**Role-Based Access Control (RBAC)**
- Implemented at two levels:
  - **Azure RBAC:** Control who can manage Azure resources (devs, admins)
  - **Application RBAC:** Control what users can do in the app

**Application-Level Permissions:**
- **Admin:** 
  - Manage users and roles
  - Access all projects
  - Configure system settings
  - View audit logs
- **Analyst:**
  - Create/edit own projects
  - Access projects they own or are assigned to
  - Run analytics
  - Export data
  - Cannot delete other users' projects
- **Viewer:**
  - Read-only access to assigned projects
  - Cannot edit questionnaires
  - Cannot run analytics
  - Can view reports

**Implementation:**
- Store user roles in PostgreSQL `users` table
- Check permissions before each action in Streamlit
- Use decorator pattern for route protection:
  ```python
  @require_role("analyst")
  def create_project():
      # Only analysts and admins can access
  ```

**6. Data Privacy & Compliance**

**PII Handling:**
- **Respondent IDs:** Hash all respondent identifiers (SHA-256 with salt)
- **IP Addresses:** Hash or truncate (store only first 3 octets)
- **Open-Ended Responses:** Flag as PII, require explicit user consent to store
- **Data Minimization:** Only collect and store data necessary for analysis

**Audit Logging:**
- Log all security-relevant events:
  - User login/logout
  - Project creation/deletion
  - Data uploads/downloads
  - Export to survey platforms
  - Analytics runs
  - Permission changes
- Store logs in Azure Monitor / Log Analytics
- Retain logs for 1 year (configurable for compliance requirements)

**Data Retention & Deletion:**
- Configurable retention policies per project
- Soft delete (move to archive) before hard delete
- User-initiated data deletion (GDPR right to be forgotten)
- Automatic deletion of temporary files after 30 days

**Compliance Certifications (Azure provides):**
- SOC 2 Type II
- ISO 27001
- GDPR compliant
- HIPAA (if Business Associate Agreement signed)

**7. API Security**

**Rate Limiting:**
- Prevent abuse of API calls (OpenAI, survey platforms)
- Implement per-user rate limits:
  - OpenAI: 100 requests/hour per user
  - Survey exports: 10 exports/hour per user
  - Data uploads: 50 MB/request, 10 requests/hour
- Use Azure API Management for advanced rate limiting (optional, $50/month)

**API Key Rotation:**
- Rotate external API keys every 90 days
- Notify users when keys are expiring
- Automate rotation where platform supports it

**Input Validation:**
- Sanitize all user inputs to prevent:
  - SQL injection (use parameterized queries)
  - XSS attacks (escape HTML in questionnaire text)
  - File upload attacks (validate file types, scan for malware)
- Validate file uploads:
  - Max file size: 100 MB
  - Allowed types: .csv, .xlsx, .sav, .json
  - Virus scanning using Azure Defender (optional)

**8. Monitoring & Incident Response**

**Azure Monitor & Application Insights**
- **Application Performance Monitoring:**
  - Track response times for all pages
  - Monitor error rates
  - Alert on abnormal patterns
- **Custom Metrics:**
  - Number of questionnaires generated
  - Analytics jobs completed
  - Export success/failure rates
- **Alerts:**
  - Email/SMS when error rate >5%
  - Alert on failed authentication attempts (possible brute force)
  - Alert on unusual data access patterns

**Security Monitoring:**
- **Azure Defender for Cloud:** 
  - Threat detection for VMs, databases, storage
  - Recommendations for security hardening
  - Cost: ~$15/month per resource
- **Log Analytics Queries:**
  - Monitor for suspicious activities:
    - Multiple failed login attempts
    - Data exports from unusual IP addresses
    - Large data downloads
  - Set up alerts for security events

**Incident Response Plan:**
1. **Detection:** Azure Monitor alerts security team
2. **Assessment:** Review audit logs to determine scope
3. **Containment:** 
   - Disable compromised user accounts
   - Rotate API keys if exposed
   - Block suspicious IP addresses
4. **Recovery:** Restore data from backups if needed
5. **Post-Incident:** Update security policies, retrain users

---

### Backup & Disaster Recovery

**Database Backups:**
- **Azure PostgreSQL:** Automated daily backups
- Retention: 7 days (can extend to 35 days)
- Point-in-time restore capability
- Geo-redundant backups (optional, for disaster recovery)

**Blob Storage:**
- **Soft Delete:** Enabled, 7-day retention (recover deleted files)
- **Versioning:** Track all changes to files
- **Geo-Replication:** Optional secondary region for disaster recovery

**Disaster Recovery Plan:**
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 24 hours (daily backups)
- **Failover Procedure:**
  1. Deploy container app to secondary Azure region
  2. Restore database from geo-redundant backup
  3. Point DNS to new region
  4. Validate functionality
  5. Notify users of temporary disruption

**Testing:**
- Quarterly disaster recovery drills
- Validate backup integrity monthly

---

### Cost Optimization

**Estimated Monthly Azure Costs (10 Concurrent Users):**

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Azure Container Apps | 2-4 instances, 4 GB RAM | $150-250 |
| Azure Database for PostgreSQL | Burstable B2s | $80-120 |
| Azure Blob Storage | Hot tier, 100 GB | $20-40 |
| Azure Key Vault | Standard | $5 |
| Azure Monitor & Insights | Pay-as-you-go | $30-50 |
| Azure AD (Basic) | Free | $0 |
| Azure Batch (low-priority) | 2-5 VMs, as-needed | $50-100 |
| **Total** | | **$335-565/month** |

**Scaling Costs (50 Concurrent Users):**
- Container Apps: $400-600/month (more instances)
- PostgreSQL: $150-250/month (higher tier)
- Blob Storage: $50-100/month (more data)
- **Total: $800-1200/month**

**Cost-Saving Strategies:**
- Use Azure Reserved Instances (1-year commitment, 30-40% discount)
- Use Azure Dev/Test pricing if available
- Implement auto-shutdown for non-production environments
- Use Cool tier for archived projects (75% cheaper storage)
- Use low-priority VMs for analytics jobs (80% discount)

---

### Deployment Architecture Diagram

```
Internet
    ↓
[Azure Front Door / Application Gateway] (Optional CDN)
    ↓
[Azure Container Apps - Streamlit Web App]
    ↓ ↓ ↓
    ↓ ↓ └→ [Azure Blob Storage] (Projects, Data, Reports)
    ↓ └→ [Azure Database for PostgreSQL] (Metadata, Users)
    └→ [Azure Key Vault] (API Keys, Secrets)
    ↓
[Azure Batch] (Heavy Analytics Jobs)
    ↓
[Azure Blob Storage] (Results)

External APIs:
- OpenAI API (GPT-4 for questionnaire generation)
- Qualtrics API (Survey export)
- Decipher API (Survey export)
- Alchemer API (Survey export)
```

**Traffic Flow:**
1. User authenticates via Azure AD
2. Streamlit app loads from Container Apps
3. User creates questionnaire → OpenAI API call → result saved to Blob Storage
4. User runs analytics → job submitted to Azure Batch → result saved to Blob Storage
5. User exports survey → API call to Qualtrics/Decipher → log saved to PostgreSQL

---

### DevOps & CI/CD

**Version Control:**
- GitHub or Azure DevOps Repos
- Branch strategy: main (production), develop (staging), feature branches

**CI/CD Pipeline (Azure DevOps or GitHub Actions):**
1. **Build Stage:**
   - Run unit tests
   - Build Docker container
   - Scan for security vulnerabilities (Dependabot, Snyk)
2. **Deploy to Staging:**
   - Deploy to staging Container Apps environment
   - Run integration tests
   - Manual approval gate
3. **Deploy to Production:**
   - Blue-green deployment (zero downtime)
   - Automatic rollback if health checks fail
   - Tag release in Git

**Infrastructure as Code:**
- Use Azure Bicep or Terraform to define all infrastructure
- Version control infrastructure definitions
- Enables reproducible deployments

---

### Alternative Considerations

**Why Not AWS or GCP?**

**Azure Advantages for This Use Case:**
- Best-in-class Active Directory integration
- Strong enterprise support and compliance
- Excellent Python SDK support
- Container Apps is cost-effective for Streamlit
- May have existing enterprise agreement with Microsoft

**AWS Would Offer:**
- More mature services (ECS, Lambda)
- Slightly cheaper compute (EC2 Spot instances)
- Better ML services (SageMaker) if adding advanced ML features

**GCP Would Offer:**
- Best for BigQuery integration (if massive datasets)
- Strong AI/ML services
- Slightly cheaper storage

**Recommendation:** Stick with Azure unless you have strong expertise in AWS/GCP or specific requirements those platforms fulfill better.

---

## Phase 1: Screener/Survey Development

### Core Requirements

**1.1 AI-Powered Questionnaire Generation**

**Input Parameters:**
- Research objectives (free text)
- Target audience demographics
- Survey length target (time/question count)
- Methodology type (attitudinal segmentation, MaxDiff, conjoint, etc.)
- Industry vertical
- Key topics to cover

**Generation Capabilities:**
- Multiple question types:
  - Single/multiple choice
  - Scale questions (Likert, semantic differential)
  - Ranking questions
  - MaxDiff sets
  - Open-ended text
  - Numeric input
  - Grid/matrix questions
- Skip logic generation
- Quota requirements
- Screening criteria

**Question ID System:**
- Format: `{METHODOLOGY}_{TOPIC}_{QTYPE}_{NUMBER}`
  - Example: `ATT_BRAND_SCALE_001` (Attitudinal, Brand, Scale, Question 1)
  - Example: `BEH_PURCHASE_MC_005` (Behavioral, Purchase, Multiple Choice, Question 5)
  - Example: `MD_FEATURES_MAXD_001` (MaxDiff, Features, MaxDiff Set, Question 1)
- Methodology codes:
  - ATT: Attitudinal (for K-means clustering)
  - BEH: Behavioral (for VarClus analysis)
  - MD: MaxDiff
  - TURF: TURF analysis inputs
  - DEM: Demographics
  - SCR: Screeners
  - OE: Open-ended

**Output Format:**
- JSON structure containing:
  ```json
  {
    "project_id": "string",
    "questionnaire_name": "string",
    "version": "string",
    "created_date": "ISO8601",
    "questions": [
      {
        "question_id": "ATT_BRAND_SCALE_001",
        "question_text": "string",
        "question_type": "scale_1to5|mc_single|mc_multi|ranking|maxdiff|open_ended|numeric|grid",
        "methodology_tag": "ATT|BEH|MD|TURF|DEM|SCR|OE",
        "response_options": [
          {
            "code": "int",
            "label": "string"
          }
        ],
        "scale_type": "likert|semantic_differential|numeric",
        "scale_anchors": {
          "min": 1,
          "max": 5,
          "min_label": "string",
          "max_label": "string"
        },
        "logic": {
          "skip_logic": [
            {
              "condition": "string",
              "target_question": "string"
            }
          ],
          "display_logic": "string",
          "randomization": "boolean",
          "required": "boolean"
        },
        "analytics_metadata": {
          "include_in_kmeans": "boolean",
          "include_in_varclus": "boolean",
          "include_in_maxdiff": "boolean",
          "include_in_turf": "boolean"
        }
      }
    ],
    "screening_criteria": [],
    "quota_requirements": []
  }
  ```

**1.2 Questionnaire Builder Interface**

**UI Components:**
- Project dashboard (list all projects)
- New project wizard
- Questionnaire editor with:
  - Question list view
  - Drag-and-drop reordering
  - In-line editing of question text
  - Response option management
  - Logic builder (visual flow chart)
  - Preview mode (respondent view)

**Editing Capabilities:**
- Add/delete/reorder questions
- Modify question types
- Edit response options
- Set skip logic visually
- Add piping/variable substitution
- Set randomization rules
- Add quota monitoring

---

## Phase 2: Screener/Survey Iterations

### Core Requirements

**2.1 Version Control**

- Automatic versioning (v1.0, v1.1, v2.0, etc.)
- Track all changes with timestamps and user attribution
- Ability to revert to previous versions
- Compare versions side-by-side
- Export change logs

**2.2 Collaboration Features**

- Comment threads on individual questions
- @mention team members
- Track review status (Draft → Review → Approved → Programmed)
- Lock questionnaire when in programming/field

**2.3 AI-Assisted Iteration**

- Natural language edit requests:
  - "Add a follow-up question about brand preference"
  - "Convert Q5 to a grid question"
  - "Add skip logic from Q3 to Q8 if response is 'No'"
- Suggested improvements from AI
- Bias detection (leading questions, order effects)

**2.4 Validation & Testing**

- Logic flow validation (no orphaned questions)
- Quota feasibility analysis
- Survey length estimation
- Mobile compatibility check
- Accessibility compliance check (WCAG 2.1)

---

## Phase 3: Survey Programming & Testing

### Core Requirements

**3.1 Platform Translation Layer**

**Supported Platforms:**

| Platform | Native Format | Export Method | Automation Level |
|----------|---------------|---------------|------------------|
| Qualtrics | .qsf (JSON) | REST API | Fully automated |
| Decipher (Forsta) | .xml | FTP/API | Semi-automated |
| Alchemer | JSON | REST API | Fully automated |
| Confirmit/Forsta Plus | .xml | REST/SOAP API | Semi-automated |

**Translation Requirements:**

**Qualtrics Integration:**
- Generate .qsf file from internal JSON
- Map question types to Qualtrics equivalents:
  - MC → Multiple Choice
  - Scale → Slider/Matrix
  - MaxDiff → Drill Down
  - Open-ended → Text Entry
- Convert skip logic to Qualtrics display logic syntax
- Set quotas using Qualtrics quota system
- API endpoint: `POST /surveys/import`
- Auto-publish survey to designated environment

**Decipher Integration:**
- Generate XML following Decipher schema
- Map survey structure to Decipher tags: `<survey>`, `<page>`, `<question>`
- Convert logic to Decipher conditions
- FTP upload to Forsta server or API POST
- Return survey URL for testing

**Alchemer Integration:**
- Direct JSON API calls to build survey
- Create survey shell: `POST /survey`
- Add questions sequentially: `POST /survey/{id}/surveyquestion`
- Set logic: `POST /survey/{id}/surveylogic`
- Activate survey: `POST /survey/{id}/surveyaction`

**Confirmit Integration:**
- Generate Confirmit XML
- SOAP/REST API upload
- Similar structure to Decipher

**3.2 Export Workflow**

**User Interface:**
1. Select platform from dropdown
2. Enter platform credentials (encrypted storage)
3. Configure platform-specific settings:
   - Survey title
   - Folder/directory location
   - Environment (test/production)
4. Click "Export to [Platform]"
5. Monitor export status
6. Receive survey link for testing

**Error Handling:**
- Validate credentials before export
- Check for unsupported question types
- Provide translation warnings
- Log all API errors
- Rollback capability

**3.3 Testing Checklist Generator**

Auto-generate testing protocol:
- [ ] All questions display correctly
- [ ] Response options load properly
- [ ] Skip logic functions as designed
- [ ] Quotas increment correctly
- [ ] Mobile rendering acceptable
- [ ] Survey completes successfully
- [ ] Data exports with correct variable names

---

## Phase 4: Tab Plan Generation

### Core Requirements

**4.1 Automatic Table Shell Creation**

**Table Structure:**
- Generate blank cross-tabulation tables
- Standard format:
  - Rows: Response options for each question
  - Columns: Banner variables (demographics, segments)
  - Cells: Placeholder for percentages and base sizes

**Table Types:**
- Frequency tables (single question)
- Cross-tabs (question by banner)
- Means tables (for numeric/scale questions)
- Top-box/Bottom-box summary tables
- Statistical significance indicators

**Output Formats:**
- Excel (.xlsx) with formatted sheets
- PowerPoint (.pptx) with table templates
- CSV for raw data import

**4.2 Banner Configuration**

**Standard Banners:**
- Total sample
- Demographics (age, gender, income, region, etc.)
- Key screening variables
- Derived segments (created post-analysis)

**User Interface:**
- Banner builder
- Add/remove banner points
- Set calculation rules (net calculations)
- Define statistical testing parameters

**4.3 Question-to-Table Mapping**

- Each question_id maps to one or more tables
- Question text becomes row stub
- Response options become row items
- Metadata tracks:
  - Which questions appear in which tables
  - Statistical test applicability
  - Formatting rules

---

## Phase 5: Data Table Population

### Core Requirements

**5.1 Data Import**

**Supported Input Formats:**
- CSV (most common)
- SPSS (.sav)
- Excel (.xlsx)
- JSON (from API exports)
- Tab-delimited text

**Import Workflow:**
1. User uploads raw data file
2. System validates against questionnaire structure
3. Match survey platform variable names to question_ids
4. Handle missing data codes
5. Validate data types (numeric, text, date)

**5.2 Data Validation**

**Validation Checks:**
- Response options match questionnaire
- No out-of-range values
- Required questions have responses
- Logic consistency (skip patterns match responses)
- Duplicate response detection
- Quota adherence
- Timestamp validation (survey duration)

**Error Reporting:**
- List all validation errors by respondent_id
- Flag suspicious patterns (straight-lining, speeders)
- Suggest data cleaning rules

**5.3 Table Population**

**Calculation Engine:**
- Frequency counts
- Percentages (column % or row %)
- Weighted vs. unweighted data
- Base size calculation (total, effective)
- Means and standard deviations
- Top-box / Bottom-box aggregations
- Net scores

**Statistical Testing:**
- Chi-square tests for categorical data
- T-tests for means
- ANOVA for multiple groups
- Confidence intervals
- Letter notation (A, B, C to show significance)
- Adjustable confidence levels (90%, 95%, 99%)

**5.4 Output Generation**

- Populate Excel table shells with calculated values
- Apply conditional formatting (highlight significant differences)
- Add footnotes (base sizes, significance levels)
- Create PowerPoint charts from tables
- Export summary statistics

---

## Phase 6: Advanced Analytics

### Core Requirements

**6.1 K-Means Clustering (Attitudinal Segmentation)**

**Purpose:** Segment respondents based on attitudinal scale questions

**Input Requirements:**
- Question_ids tagged with `methodology_tag: "ATT"`
- All attitudinal scale questions (typically 1-5 or 1-7 scales)
- Minimum sample size: 200 respondents (recommend 500+)

**Algorithm Parameters:**
- Number of clusters: User-defined (2-10), with elbow method recommendation
- Initialization method: K-means++
- Distance metric: Euclidean
- Max iterations: 300
- Convergence criterion: 0.0001

**Process:**
1. Extract all ATT-tagged questions from dataset
2. Handle missing data (mean imputation or listwise deletion)
3. Standardize variables (z-scores)
4. Run K-means clustering
5. Generate cluster profiles (means for each variable by cluster)
6. Calculate cluster sizes
7. Assign cluster membership to each respondent

**Outputs:**
- Cluster membership variable (added to dataset)
- Cluster profile table (mean scores by cluster)
- Cluster size distribution
- Within-cluster sum of squares
- Silhouette scores (cluster quality metric)
- Cluster naming suggestions from AI based on profiles
- Visualization: Cluster means heatmap

**6.2 VarClus (Variable Clustering for Behavioral Groupings)**

**Purpose:** Identify underlying behavioral dimensions from multiple related questions

**Input Requirements:**
- Question_ids tagged with `methodology_tag: "BEH"`
- Behavioral questions (purchase behaviors, usage patterns, etc.)
- Can handle mix of binary and multi-category questions

**Algorithm:**
- Hierarchical clustering of variables (not respondents)
- Oblique or orthogonal rotation options
- Maximum eigenvalue criterion for cluster retention

**Process:**
1. Extract all BEH-tagged questions
2. Calculate correlation matrix
3. Perform variable clustering
4. Determine optimal number of clusters (eigenvalue > 1)
5. Assign variables to clusters
6. Calculate cluster summaries (composite scores)

**Outputs:**
- Variable-to-cluster assignments
- Cluster correlation structure
- R-squared for each variable
- Composite score for each cluster (factor score)
- Add composite scores to dataset as new variables
- Tree diagram of variable clustering
- AI-generated cluster interpretations

**6.3 MaxDiff Analysis (Utility Scores)**

**Purpose:** Calculate preference utilities for MaxDiff exercises

**Input Requirements:**
- Question_ids tagged with `methodology_tag: "MD"`
- MaxDiff sets (respondents choose best and worst from sets of items)
- Experimental design matrix (which items appeared in which sets)

**Algorithm:**
- Hierarchical Bayes (HB) estimation
- Alternative: Counting analysis (simpler but less robust)

**Process:**
1. Extract MaxDiff data
2. Validate design (balanced appearance of items)
3. Run HB estimation to calculate utilities
4. Rescale utilities (zero-centered or 0-100 scale)
5. Calculate standard errors
6. Derive preference shares (probability of being chosen)

**Outputs:**
- Item-level utility scores (mean and distribution)
- Individual-level utilities (if HB used)
- Preference shares (%)
- Rank order of items
- Segment-level utilities (if clusters defined)
- Visualization: Utility score bar chart
- Statistical significance of differences

**6.4 TURF Analysis (Total Unduplicated Reach & Frequency)**

**Purpose:** Optimize product/feature portfolios to maximize reach

**Input Requirements:**
- Question_ids tagged with `methodology_tag: "TURF"`
- Binary acceptance data (respondent would/wouldn't use each item)
- Minimum 5 items, maximum 50 items

**Algorithm:**
- Exhaustive search for small item sets (≤5 items)
- Heuristic search for larger sets (greedy or genetic algorithm)

**Parameters:**
- Portfolio size: User-defined (1-10 items)
- Optimization metric: Reach (default) or Frequency

**Process:**
1. Extract TURF-tagged questions
2. Create binary acceptance matrix
3. Run optimization to find best combination
4. Calculate reach and frequency for each combination
5. Rank combinations by reach
6. Calculate incremental reach for adding items

**Outputs:**
- Optimal portfolio (list of items)
- Reach % for optimal portfolio
- Average frequency
- Reach-frequency curve
- Incremental reach table (reach of 1 item, 2 items, 3 items, etc.)
- Item contribution analysis (marginal reach added by each item)
- Visualization: Reach bars by portfolio size

**6.5 Significance Testing**

**Purpose:** Identify statistically significant differences between groups

**Test Types:**
- Proportions: Z-test, Chi-square
- Means: Independent samples t-test, paired t-test, ANOVA
- Post-hoc tests: Tukey HSD, Bonferroni

**Configuration:**
- Confidence level: 90%, 95%, 99%
- Multiple comparison adjustment: Bonferroni, Holm, or none
- Banner-to-banner or question-to-banner

**Outputs:**
- Significance letters (A, B, C, etc.)
- P-values
- Confidence intervals
- Effect sizes (Cohen's d, Cramer's V)

**6.6 Additional Analyses (Future Expansion)**

**Framework for Adding New Methods:**
- Each new analysis type requires:
  - Question ID tagging system
  - Input data structure definition
  - Algorithm selection
  - Parameter configuration UI
  - Output format specification
  - Validation rules

**Planned Additions:**
- Conjoint analysis (choice-based or adaptive)
- Factor analysis (EFA/CFA)
- Regression modeling (linear, logistic)
- Correspondence analysis
- Perceptual mapping
- Time series analysis (tracking studies)
- Text analytics (sentiment analysis, topic modeling for open-ends)

---

## Technical Implementation Details

### 6.7 Analytics Module Architecture

**Python Libraries:**
- `pandas`: Data manipulation
- `numpy`: Numerical computing
- `scikit-learn`: K-means, PCA, scaling
- `scipy`: Statistical tests
- `statsmodels`: Advanced statistics, regression
- `pyrsm`: MaxDiff analysis (or custom implementation)
- TURF: Custom Python implementation
- VarClus: Port from SAS or custom implementation

**Code Structure:**
```
/analytics
  /clustering
    - kmeans.py
    - varclus.py
  /preference
    - maxdiff.py
    - turf.py
  /statistics
    - significance_tests.py
    - descriptive_stats.py
  /utils
    - data_preparation.py
    - validation.py
    - export.py
```

**Each Analysis Module Requires:**
1. Input validation function
2. Data preprocessing function
3. Core algorithm implementation
4. Output formatting function
5. Visualization function
6. Error handling
7. Unit tests

---

## Reporting & Visualization

### Core Requirements

**7.1 Automated Report Generation**

**Output Formats:**
- PowerPoint (.pptx)
- PDF
- Interactive HTML dashboard

**Report Sections:**
- Executive summary (AI-generated)
- Methodology overview
- Sample profile (demographics)
- Key findings by research objective
- Detailed results (charts and tables)
- Statistical appendix
- Verbatim comments (open-ended responses)

**7.2 Visualization Library**

**Chart Types:**
- Bar charts (horizontal and vertical)
- Stacked bar charts
- Line charts (tracking)
- Scatter plots
- Heatmaps (cluster profiles)
- Tree diagrams (VarClus)
- Perceptual maps (2D)

**Customization:**
- Brand color palettes
- Chart templates
- Automatic chart selection based on data type

**7.3 Interactive Dashboards**

- Filter by segments, demographics
- Drill-down into sub-groups
- Export individual charts
- Real-time recalculation

---

## Data Management & Security

### Core Requirements

**8.1 Data Storage**

**File Structure:**
```
/projects
  /{project_id}
    /questionnaires
      - v1.0.json
      - v1.1.json
    /data
      - raw_data.csv
      - cleaned_data.csv
      - respondent_ids.csv (hashed)
    /outputs
      /tables
      /analytics
      /reports
    /exports
      - qualtrics_export.qsf
      - decipher_export.xml
```

**Database Schema:**
- Projects table (project metadata)
- Questionnaires table (versions, timestamps)
- Users table (authentication)
- Analytics_runs table (track analysis history)
- Exports_log table (track platform uploads)

**8.2 Security & Privacy**

**Data Protection:**
- Encrypt data at rest (AES-256)
- Encrypt data in transit (TLS 1.3)
- Hash respondent IDs (SHA-256)
- No storage of PII unless explicitly required
- Automatic data retention policies (delete after X months)

**Access Control:**
- User authentication required
- Role-based permissions (Admin, Analyst, Viewer)
- Project-level access control
- Audit logs (who accessed what, when)

**API Key Management:**
- Encrypted storage of platform credentials
- Per-user API keys (not shared)
- Key rotation policy
- Secure input (passwords never displayed)

**8.3 Backup & Recovery**

- Daily automated backups
- Version history for all project files
- Disaster recovery plan
- Data export functionality (take your data anywhere)

---

## User Interface Design

### Core Requirements

**9.1 Streamlit App Structure**

**Main Navigation:**
- Home / Dashboard
- Projects (list view)
- New Project
- Analytics Hub
- Settings
- Help / Documentation

**Project Workspace:**
- Tabs: Questionnaire | Export | Data | Tables | Analytics | Reports
- Sidebar: Project details, quick actions, status indicators

**9.2 Key UI Components**

**Questionnaire Builder:**
- Question list (left panel)
- Question editor (center panel)
- Preview (right panel or toggle)
- Logic visualizer (modal or dedicated tab)

**Data Upload:**
- Drag-and-drop file upload
- Column mapping interface (match survey vars to question_ids)
- Validation results display

**Analytics Dashboard:**
- Analysis type selector (cards or buttons)
- Parameter configuration form
- Run analysis button
- Results display (tables, charts)
- Export options

**9.3 User Experience Principles**

- Minimize clicks to complete tasks
- Progressive disclosure (show advanced options only when needed)
- Real-time validation feedback
- Clear error messages with suggested fixes
- Contextual help tooltips
- Keyboard shortcuts for power users

---

## Performance & Scalability

### Core Requirements

**10.1 Concurrent User Support**

**Session Management:**
- Isolated session state per user
- No data leakage between users
- Session timeout after inactivity

**Resource Allocation:**
- Queue long-running analytics jobs
- Display progress indicators
- Allow cancellation of running jobs
- Email notification when analysis completes

**10.2 Optimization**

**Data Processing:**
- Use pandas vectorized operations (avoid loops)
- Implement data chunking for large datasets (>100k rows)
- Cache frequently accessed data (questionnaire structure)
- Lazy loading (load data only when needed)

**API Calls:**
- Rate limiting (respect platform API limits)
- Retry logic with exponential backoff
- Batch operations where possible
- Asynchronous processing (don't block UI)

**10.3 Monitoring**

- Application performance monitoring (response times)
- Error tracking (log all exceptions)
- Usage analytics (which features are used most)
- System health checks (disk space, memory, API status)

---

## Testing & Quality Assurance

### Core Requirements

**11.1 Testing Strategy**

**Unit Tests:**
- Test each analytics function independently
- Validate data transformations
- Test edge cases (empty data, single respondent, etc.)

**Integration Tests:**
- Test full workflow (questionnaire → export → import → analysis)
- Test API integrations (mocked and live)
- Test database operations

**User Acceptance Testing:**
- Real users test with real projects
- Collect feedback on usability
- Identify edge cases not caught in development

**11.2 Test Data**

- Create synthetic datasets for testing:
  - Small (100 respondents)
  - Medium (1,000 respondents)
  - Large (10,000+ respondents)
- Cover all question types
- Include realistic skip logic patterns
- Simulate common data quality issues

---

## Documentation Requirements

### Core Requirements

**12.1 User Documentation**

**Getting Started Guide:**
- Account setup
- Creating first project
- Basic workflow walkthrough
- Video tutorials

**Feature Documentation:**
- Questionnaire development tips
- Survey platform export guides
- Data import troubleshooting
- Analytics interpretation guides
- Report customization

**12.2 Technical Documentation**

**For Developers (Future Maintenance):**
- System architecture diagram
- Database schema
- API documentation (internal functions)
- Adding new analytics modules (developer guide)
- Adding new survey platforms
- Deployment guide

**12.3 Help System**

- In-app contextual help (? icons)
- FAQ section
- Troubleshooting guide
- Contact support (email or ticketing system)

---

## Phased Implementation Plan

### Phase 0: Azure Infrastructure Setup (Weeks 1-2)
- Create Azure subscription and resource group
- Set up Azure Active Directory tenant
- Provision Azure Container Apps (or App Service)
- Provision Azure Database for PostgreSQL
- Configure Azure Blob Storage with containers
- Set up Azure Key Vault
- Configure Azure Monitor and Application Insights
- Set up VNet and network security groups
- Configure CI/CD pipeline (Azure DevOps or GitHub Actions)
- Set up development, staging, and production environments

### Phase 1: Foundation (Weeks 3-6)
- Set up local development environment (Python, Docker)
- Integrate Azure AD authentication with Streamlit
- Build user management (roles, permissions)
- Create database schema and migrations
- Implement Azure Blob Storage integration
- Build project management system
- Implement questionnaire JSON structure
- Build basic Streamlit UI with session management
- Test concurrent user sessions (simulate 10 users)

### Phase 2: Questionnaire Builder (Weeks 7-10)
- Integrate OpenAI API via Azure Key Vault
- Build AI questionnaire generation with prompt engineering
- Implement question editor UI with drag-and-drop
- Build logic builder (skip logic, display logic)
- Implement question ID tagging system
- Add version control and change tracking
- Build preview mode (respondent view)
- Unit tests for questionnaire generation

### Phase 3: Platform Exports (Weeks 11-15)
- Develop translation layer architecture
- Implement Qualtrics integration:
  - JSON to .qsf converter
  - REST API export
  - Test with Qualtrics sandbox
- Implement Decipher/Forsta integration:
  - JSON to XML converter
  - API/FTP upload
- Add Alchemer export (JSON API)
- Build export testing workflow UI
- Error handling and rollback
- Store API credentials in Key Vault
- Integration tests with all platforms

### Phase 4: Data & Tables (Weeks 16-20)
- Build data upload UI (drag-and-drop)
- Implement data validation engine
- Create table shell generator (blank crosstabs)
- Implement table population with statistical calculations
- Add significance testing (chi-square, t-tests, ANOVA)
- Build banner configuration UI
- Export to Excel with formatting
- Data quality reporting (speeders, straight-liners)

### Phase 5: Analytics (Weeks 21-28)
- Set up Azure Batch for heavy analytics (optional)
- Implement K-means clustering module:
  - Data preparation
  - Algorithm execution
  - Cluster profiling
  - Visualization
- Implement MaxDiff analysis module:
  - HB estimation or counting analysis
  - Utility score calculation
  - Preference shares
- Implement TURF analysis module:
  - Optimization algorithm
  - Reach-frequency calculation
- Implement VarClus module (custom or R integration):
  - Variable clustering
  - Factor scores
- Build analytics dashboard UI
- Add job queue and progress tracking
- Unit tests for all analytics modules
- Validate against known results (test datasets)

### Phase 6: Reporting (Weeks 29-32)
- Build PowerPoint report generator (python-pptx)
- Create chart generation library (matplotlib/plotly)
- Implement automated report templates
- Add PDF export functionality
- Build interactive dashboard (optional: Plotly Dash)
- Template customization UI
- Integration tests for report generation

### Phase 7: Testing & Launch (Weeks 33-36)
- Security audit (penetration testing, vulnerability scan)
- Load testing (simulate 10-20 concurrent users)
- User acceptance testing with pilot group
- Performance optimization based on test results
- Bug fixes and refinements
- Complete user documentation and video tutorials
- Deploy to production Azure environment
- Soft launch with 3-5 pilot users
- Monitor production metrics for 2 weeks
- Full launch

---

## Success Metrics

**Efficiency Gains:**
- Survey programming time: Reduce from 4 hours to 15 minutes
- Table generation time: Reduce from 2 hours to 5 minutes
- Data population time: Reduce from 1 hour to 5 minutes
- Analytics run time: Reduce from 3 hours to 10 minutes

**Quality Metrics:**
- Zero programming errors in exported surveys
- Data validation catches 100% of structural errors
- Analytics reproducibility: 100% match vs. manual calculations

**Adoption Metrics:**
- 10 concurrent users supported without performance degradation
- 90%+ of projects use full workflow (end-to-end)
- 80%+ user satisfaction score

---

## Risk Assessment & Mitigation

**Technical Risks:**

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API rate limits exceeded | High | Medium | Implement queue, caching, user education |
| Platform API changes | High | Medium | Version pinning, monitoring, modular design |
| Large dataset performance | Medium | High | Data chunking, progress indicators, optimization |
| Analytics algorithm errors | High | Low | Extensive testing, validation against known results |

**Business Risks:**

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Platform doesn't support feature | Medium | Medium | Document limitations, offer workarounds |
| User data loss | Critical | Low | Daily backups, version control, recovery plan |
| Security breach | Critical | Low | Encryption, access controls, security audit |
| Concurrent user conflicts | Medium | Medium | Session isolation, file locking, clear UX |

---

## Future Enhancements (Post-Launch)

**Version 2.0 Features:**
- Real-time collaboration (multiple users editing same questionnaire)
- AI-powered data quality checks (detect fraudulent responses)
- Automated storytelling (AI writes full reports)
- Integration with additional platforms (Microsoft Forms, Typeform)
- Mobile app for project monitoring
- Client portal (share results with stakeholders)

**Version 3.0 Features:**
- Predictive modeling (forecast market trends)
- Automated survey fielding (manage panel providers via API)
- Real-time dashboards during fielding
- Advanced text analytics (NLP for open-ended responses)
- Integration with BI tools (Tableau, Power BI)

---

## Appendix: Technical Specifications

### A. Question Type Definitions

| Type | Description | Response Format | Analytics Use |
|------|-------------|-----------------|---------------|
| scale_1to5 | Likert scale | Integer 1-5 | K-means, means, sig testing |
| mc_single | Single choice | Integer (code) | Frequency, cross-tabs, sig testing |
| mc_multi | Multiple choice | Array of integers | Frequency, cross-tabs |
| ranking | Rank order | Array of integers | Rank analysis |
| maxdiff | MaxDiff set | {best: int, worst: int} | MaxDiff utility scores |
| open_ended | Text entry | String | Text analytics |
| numeric | Numeric input | Float | Means, regression |
| grid | Matrix question | Object {row: code, col: code} | Cross-tabs, factor analysis |

### B. API Endpoint Summary

**OpenAI API:**
- POST /v1/chat/completions (questionnaire generation)

**Qualtrics API:**
- POST /surveys/import (upload survey)
- GET /surveys/{id} (retrieve survey details)

**Decipher API:**
- POST /upload (FTP upload)
- GET /survey/{id}/status (check status)

**Alchemer API:**
- POST /survey (create survey)
- POST /survey/{id}/surveyquestion (add question)
- POST /survey/{id}/surveyaction (activate)

### C. Data Dictionary

**Questionnaire JSON Fields:**
- project_id: UUID
- questionnaire_name: String (max 255 chars)
- version: Semantic version string (e.g., "1.2.0")
- created_date: ISO8601 timestamp
- questions: Array of question objects
- screening_criteria: Array of screening objects
- quota_requirements: Array of quota objects

**Question Object Fields:**
- question_id: String (format: {METHOD}_{TOPIC}_{QTYPE}_{NUM})
- question_text: String (max 1000 chars)
- question_type: Enum (see Question Type Definitions)
- methodology_tag: Enum (ATT, BEH, MD, TURF, DEM, SCR, OE)
- response_options: Array of {code: int, label: string}
- logic: Object containing skip/display logic
- analytics_metadata: Object with boolean flags

### D. Statistical Test Reference

**Chi-Square Test:**
- Use case: Compare proportions across groups
- Assumptions: Expected cell count ≥ 5
- Output: Chi-square statistic, p-value, Cramer's V

**Independent Samples T-Test:**
- Use case: Compare means between two groups
- Assumptions: Normal distribution, equal variances (or Welch's correction)
- Output: T-statistic, p-value, Cohen's d, confidence interval

**ANOVA:**
- Use case: Compare means across 3+ groups
- Assumptions: Normal distribution, homogeneity of variance
- Output: F-statistic, p-value, eta-squared
- Post-hoc: Tukey HSD or Bonferroni for pairwise comparisons

---

## Developer Prerequisites & Setup

### Required Skills

**Essential:**
- Python 3.10+ (intermediate level)
- Streamlit framework basics
- REST API integration
- SQL (PostgreSQL)
- Git version control
- Docker basics (for containerization)

**Recommended:**
- Azure cloud services experience
- Statistical analysis (pandas, numpy, scikit-learn)
- Data visualization (matplotlib, plotly)
- CI/CD pipelines (Azure DevOps or GitHub Actions)

**Nice to Have:**
- Survey platform experience (Qualtrics, Decipher)
- Machine learning algorithms (clustering, factor analysis)
- PowerPoint automation (python-pptx)

### Development Environment Setup

**Local Development (Windows/Mac/Linux):**

1. **Install Required Software:**
   ```bash
   # Python 3.10+
   python --version
   
   # Install Poetry (dependency management)
   pip install poetry
   
   # Install Azure CLI
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   
   # Install Docker Desktop
   # Download from: https://www.docker.com/products/docker-desktop
   
   # Install Visual Studio Code (recommended IDE)
   # Download from: https://code.visualstudio.com/
   ```

2. **Clone Repository:**
   ```bash
   git clone https://github.com/your-org/research-automation-platform.git
   cd research-automation-platform
   ```

3. **Set Up Python Environment:**
   ```bash
   # Create virtual environment
   poetry install
   
   # Or with pip:
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Create `.env` file in project root:
   ```
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-client-id
   AZURE_CLIENT_SECRET=your-client-secret
   DATABASE_URL=postgresql://user:password@localhost:5432/research_platform
   BLOB_STORAGE_CONNECTION_STRING=your-connection-string
   OPENAI_API_KEY=your-openai-key  # For local dev only, use Key Vault in production
   ```

5. **Set Up Local Database:**
   ```bash
   # Install PostgreSQL locally
   # Or use Docker:
   docker run --name research-postgres -e POSTGRES_PASSWORD=devpassword -p 5432:5432 -d postgres:15
   
   # Run migrations
   python manage.py migrate
   ```

6. **Run Application Locally:**
   ```bash
   streamlit run app.py
   # App will open at http://localhost:8501
   ```

### Azure Setup (First-Time)

**1. Create Azure Resources:**

```bash
# Login to Azure
az login

# Create resource group
az group create --name rg-research-platform --location eastus

# Create PostgreSQL database
az postgres flexible-server create \
  --resource-group rg-research-platform \
  --name research-platform-db \
  --location eastus \
  --admin-user dbadmin \
  --admin-password <SecurePassword> \
  --sku-name Standard_B2s \
  --tier Burstable \
  --version 15

# Create storage account
az storage account create \
  --name researchplatformstorage \
  --resource-group rg-research-platform \
  --location eastus \
  --sku Standard_LRS

# Create blob container
az storage container create \
  --name research-platform-data \
  --account-name researchplatformstorage

# Create Key Vault
az keyvault create \
  --name research-platform-kv \
  --resource-group rg-research-platform \
  --location eastus

# Store secrets in Key Vault
az keyvault secret set --vault-name research-platform-kv --name openai-api-key --value "<your-key>"
az keyvault secret set --vault-name research-platform-kv --name qualtrics-api-key --value "<your-key>"
```

**2. Create Container App:**

```bash
# Create Container Apps environment
az containerapp env create \
  --name research-platform-env \
  --resource-group rg-research-platform \
  --location eastus

# Build and push Docker image
docker build -t researchplatform.azurecr.io/research-app:v1 .
docker push researchplatform.azurecr.io/research-app:v1

# Create Container App
az containerapp create \
  --name research-platform-app \
  --resource-group rg-research-platform \
  --environment research-platform-env \
  --image researchplatform.azurecr.io/research-app:v1 \
  --target-port 8501 \
  --ingress external \
  --min-replicas 2 \
  --max-replicas 10
```

**3. Configure Azure AD Authentication:**

```bash
# Register application in Azure AD
az ad app create --display-name "Research Platform"

# Get Application ID and configure in Streamlit app
# Follow guide: https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app
```

### Project Structure

```
research-automation-platform/
│
├── app.py                          # Main Streamlit application entry point
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container definition
├── .env.example                    # Example environment variables
│
├── config/
│   ├── settings.py                 # Application configuration
│   └── azure_config.py             # Azure service connections
│
├── auth/
│   ├── azure_ad.py                 # Azure AD authentication
│   └── permissions.py              # RBAC implementation
│
├── database/
│   ├── models.py                   # SQLAlchemy models
│   ├── migrations/                 # Database migration scripts
│   └── db_connection.py            # Database connection management
│
├── questionnaire/
│   ├── generator.py                # OpenAI questionnaire generation
│   ├── editor.py                   # Questionnaire editing logic
│   ├── validator.py                # Questionnaire validation
│   └── question_types.py           # Question type definitions
│
├── exports/
│   ├── base_translator.py          # Base translation class
│   ├── qualtrics_export.py         # Qualtrics integration
│   ├── decipher_export.py          # Decipher integration
│   ├── alchemer_export.py          # Alchemer integration
│   └── confirmit_export.py         # Confirmit integration
│
├── data/
│   ├── importer.py                 # Data upload and validation
│   ├── validator.py                # Data quality checks
│   └── cleaner.py                  # Data cleaning utilities
│
├── tables/
│   ├── generator.py                # Table shell generation
│   ├── population.py               # Table population with data
│   └── statistical_tests.py       # Significance testing
│
├── analytics/
│   ├── clustering/
│   │   ├── kmeans.py               # K-means clustering
│   │   └── varclus.py              # Variable clustering
│   ├── preference/
│   │   ├── maxdiff.py              # MaxDiff analysis
│   │   └── turf.py                 # TURF analysis
│   └── utils/
│       ├── data_prep.py            # Data preparation utilities
│       └── visualization.py        # Analytics visualization
│
├── reporting/
│   ├── pptx_generator.py           # PowerPoint report generation
│   ├── pdf_generator.py            # PDF export
│   └── templates/                  # Report templates
│
├── ui/
│   ├── pages/
│   │   ├── home.py                 # Dashboard page
│   │   ├── projects.py             # Project management page
│   │   ├── questionnaire.py        # Questionnaire builder page
│   │   ├── export.py               # Export page
│   │   ├── data.py                 # Data upload page
│   │   ├── tables.py               # Table generation page
│   │   ├── analytics.py            # Analytics page
│   │   └── reports.py              # Reports page
│   └── components/
│       ├── sidebar.py              # Navigation sidebar
│       ├── question_editor.py      # Question editing component
│       └── data_viewer.py          # Data viewing component
│
├── storage/
│   ├── blob_storage.py             # Azure Blob Storage integration
│   └── file_manager.py             # File upload/download management
│
├── utils/
│   ├── logger.py                   # Logging configuration
│   ├── exceptions.py               # Custom exceptions
│   └── helpers.py                  # Helper functions
│
└── tests/
    ├── test_questionnaire.py
    ├── test_exports.py
    ├── test_analytics.py
    └── test_integration.py
```

### Key Python Packages

```
# requirements.txt
streamlit==1.32.0
pandas==2.2.0
numpy==1.26.3
scikit-learn==1.4.0
scipy==1.12.0
statsmodels==0.14.1
openpyxl==3.1.2                     # Excel file handling
python-pptx==0.6.23                 # PowerPoint generation
azure-identity==1.15.0              # Azure authentication
azure-keyvault-secrets==4.7.0       # Key Vault access
azure-storage-blob==12.19.0         # Blob Storage
psycopg2-binary==2.9.9              # PostgreSQL driver
sqlalchemy==2.0.25                  # ORM
msal==1.26.0                        # Microsoft Authentication Library
requests==2.31.0                    # HTTP requests for APIs
python-dotenv==1.0.0                # Environment variable management
pytest==8.0.0                       # Testing
plotly==5.18.0                      # Interactive visualizations
matplotlib==3.8.2                   # Static plots
seaborn==0.13.2                     # Statistical visualization
```

### Testing Strategy

**Unit Tests:**
```bash
# Run all tests
pytest

# Run specific module
pytest tests/test_analytics.py

# Run with coverage
pytest --cov=analytics tests/
```

**Integration Tests:**
```bash
# Test with local database
pytest tests/test_integration.py --local-db

# Test with staging Azure resources
pytest tests/test_integration.py --staging
```

**Load Testing:**
```bash
# Use Locust for load testing
pip install locust
locust -f tests/load_test.py --host http://localhost:8501
```

---

## Glossary

**Attitudinal Segmentation:** Grouping respondents based on shared attitudes/beliefs using cluster analysis

**Banner:** A set of demographic or segment variables used as columns in cross-tabulation tables

**K-Means:** Clustering algorithm that partitions data into k groups by minimizing within-cluster variance

**MaxDiff:** Maximum Difference Scaling, a method to measure preferences by asking respondents to choose best and worst options

**Significance Testing:** Statistical tests to determine if differences between groups are likely due to chance

**Skip Logic:** Survey logic that determines which questions respondents see based on previous answers

**TURF:** Total Unduplicated Reach and Frequency, an analysis to optimize product portfolios

**VarClus:** Variable Clustering, a method to group related variables into dimensions

**Utility Score:** A numerical value representing the preference or desirability of an attribute in MaxDiff or conjoint analysis

---

**End of Requirements Document**
