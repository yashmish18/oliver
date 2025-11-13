class ExamRoomOrchestrator {
    constructor() {
        this.currentStep = 1;
        this.state = {
            enrollmentRows: [],
            rooms: [],
            selectedAlgorithm: 'smart',
            maxCoursesPerRoom: 3,
            slotCapacityMode: 'greedy',
            selectedSemesters: new Set(),
            selectedCourses: new Set(),
            availableSemesters: [],
            availableCoursesBySemester: new Map(),
            courseLookup: new Map(),
            slotTemplates: [],
            slotInstances: [],
            filteredStudents: [],
            assignments: []
        };
        this.elements = this.cacheElements();
        this.charts = {
            utilization: null,
            distribution: null
        };
        this.notificationTimeout = null;
        this.init();
    }

    cacheElements() {
        return {
            wizardSteps: Array.from(document.querySelectorAll('.wizard-step')),
            stepSections: Array.from(document.querySelectorAll('.step')),
            nextBtn: document.getElementById('next-step'),
            prevBtn: document.getElementById('prev-step'),

            // Metrics
            metricStudents: document.querySelector('#metric-students .metric-value'),
            metricRooms: document.querySelector('#metric-rooms .metric-value'),
            metricCapacity: document.querySelector('#metric-capacity .metric-value'),

            // Uploads
            enrollmentInput: document.getElementById('enrollment-input'),
            roomsInput: document.getElementById('rooms-input'),
            enrollmentPreview: document.getElementById('enrollment-preview'),
            roomsPreview: document.getElementById('rooms-preview'),
            loadEnrollmentSample: document.getElementById('load-enrollment-sample'),
            loadRoomsSample: document.getElementById('load-rooms-sample'),

            // Algorithm (step 2)
            algorithmRadios: Array.from(document.querySelectorAll('input[name="algorithm"]')),
            maxCoursesInput: document.getElementById('max-courses'),
            slotCapacityMode: document.getElementById('slot-capacity-mode'),
            seedInput: document.getElementById('seed'),

            // Filters (step 3)
            filtersContainer: document.getElementById('filters-container'),
            clearSemestersBtn: document.getElementById('clear-semesters'),
            clearCoursesBtn: document.getElementById('clear-courses'),
            semesterSummary: document.getElementById('semester-summary'),
            courseSummary: document.getElementById('course-summary'),
            filterNote: document.getElementById('filter-note'),

            // Schedule inputs
            scheduleStart: document.getElementById('schedule-start'),
            scheduleEnd: document.getElementById('schedule-end'),
            slotsPerDayInput: document.getElementById('slots-per-day'),
            slotConfigContainer: document.getElementById('slot-config'),
            addSlotTemplateBtn: document.getElementById('add-slot-template'),

            // Results (step 4)
            resultsCard: document.getElementById('results-card'),
            resultsContainer: document.getElementById('results-container'),
            exportCsvBtn: document.getElementById('export-csv'),
            exportExcelBtn: document.getElementById('export-excel'),
            exportPdfBtn: document.getElementById('export-pdf'),

            // Analytics
            analyticsCard: document.getElementById('analytics-card'),
            overallUtilization: document.getElementById('overall-utilization'),
            unassignedCount: document.getElementById('unassigned-count'),
            highUtilCount: document.getElementById('high-util-count'),
            lowUtilCount: document.getElementById('low-util-count'),
            aiSummary: document.getElementById('ai-summary'),
            utilizationChart: document.getElementById('utilization-chart'),
            distributionChart: document.getElementById('slot-distribution-chart'),

            // Notifications
            notificationBanner: document.getElementById('notification-banner'),
            notificationMessage: document.querySelector('#notification-banner .notification-message'),
            dismissNotification: document.getElementById('dismiss-notification')
        };
    }

    init() {
        this.bindStepNavigation();
        this.bindUploadControls();
        this.bindAlgorithmControls();
        this.bindFilterControls();
        this.bindSlotControls();
        this.bindExportControls();
        this.bindNotificationControls();
        this.initializeDefaultSlots();
        this.updateStepUI();
    }

    bindStepNavigation() {
        if (this.elements.nextBtn) {
            this.elements.nextBtn.addEventListener('click', () => {
                this.handleNextStep();
            });
        }
        if (this.elements.prevBtn) {
            this.elements.prevBtn.addEventListener('click', () => {
                this.goToStep(Math.max(1, this.currentStep - 1));
            });
        }
        this.elements.wizardSteps.forEach(step => {
            step.addEventListener('click', () => {
                const targetStep = Number(step.dataset.step);
                if (this.canNavigateToStep(targetStep)) {
                    if (targetStep > this.currentStep) {
                        this.handleNextStep(targetStep - this.currentStep);
                    } else {
                        this.goToStep(targetStep);
                    }
                }
            });
        });
    }

    bindUploadControls() {
        const { enrollmentInput, roomsInput, loadEnrollmentSample, loadRoomsSample } = this.elements;
        if (enrollmentInput) {
            enrollmentInput.addEventListener('change', (event) => {
                const file = event.target.files && event.target.files[0];
                if (file) {
                    this.loadEnrollmentFile(file);
                }
            });
        }
        if (roomsInput) {
            roomsInput.addEventListener('change', (event) => {
                const file = event.target.files && event.target.files[0];
                if (file) {
                    this.loadRoomFile(file);
                }
            });
        }
        if (loadEnrollmentSample) {
            loadEnrollmentSample.addEventListener('click', () => {
                this.fetchSampleCSV('processed_enrollment.csv')
                    .then(({ records }) => this.applyEnrollmentData(records))
                    .catch(error => this.notify(`Unable to load sample enrollment data (${error.message}). Please ensure you are serving the app from a local or remote web server.`, 'error'));
            });
        }
        if (loadRoomsSample) {
            loadRoomsSample.addEventListener('click', () => {
                this.fetchSampleCSV('rooms_config.csv')
                    .then(({ records }) => this.applyRoomData(records))
                    .catch(error => this.notify(`Unable to load sample room data (${error.message}). Please ensure you are serving the app from a local or remote web server.`, 'error'));
            });
        }
    }

    bindAlgorithmControls() {
        const { algorithmRadios, maxCoursesInput, slotCapacityMode } = this.elements;
        if (algorithmRadios.length) {
            algorithmRadios.forEach(radio => {
                radio.addEventListener('change', (event) => {
                    if (event.target.checked) {
                        this.state.selectedAlgorithm = event.target.value;
                    }
                });
            });
        }
        if (maxCoursesInput) {
            maxCoursesInput.addEventListener('change', (event) => {
                const value = Number(event.target.value);
                this.state.maxCoursesPerRoom = Number.isFinite(value) && value > 0 ? value : 1;
                if (this.state.maxCoursesPerRoom < 1) {
                    this.state.maxCoursesPerRoom = 1;
                }
                event.target.value = this.state.maxCoursesPerRoom;
            });
        }
        if (slotCapacityMode) {
            slotCapacityMode.addEventListener('change', (event) => {
                this.state.slotCapacityMode = event.target.value || 'greedy';
            });
        }
    }

    bindFilterControls() {
        const { clearSemestersBtn, clearCoursesBtn, filtersContainer, filterNote } = this.elements;
        if (clearSemestersBtn) {
            clearSemestersBtn.addEventListener('click', () => {
                this.state.selectedSemesters.clear();
                this.state.selectedCourses.clear();
                if (filtersContainer) {
                    filtersContainer.querySelectorAll('input[data-filter="semester"]').forEach(input => {
                        input.checked = false;
                        input.closest('.filter-item')?.classList.remove('filter-item--selected');
                    });
                    filtersContainer.querySelectorAll('input[data-filter="course"]').forEach(input => {
                        input.checked = false;
                        input.disabled = true;
                        input.closest('.filter-item')?.classList.remove('filter-item--selected');
                    });
                }
                this.updateFilterSummaries();
                this.updateFilterNote();
            });
        }

        if (clearCoursesBtn) {
            clearCoursesBtn.addEventListener('click', () => {
                this.state.selectedCourses.clear();
                if (filtersContainer) {
                    filtersContainer.querySelectorAll('input[data-filter="course"]').forEach(input => {
                        input.checked = false;
                        input.closest('.filter-item')?.classList.remove('filter-item--selected');
                    });
                }
                this.updateFilterSummaries();
                this.updateFilterNote();
            });
        }

        if (filterNote) {
            filterNote.textContent = 'No filters selected. All courses and semesters will be considered.';
        }
    }

    bindSlotControls() {
        const { scheduleStart, scheduleEnd, slotsPerDayInput, addSlotTemplateBtn } = this.elements;
        if (scheduleStart) {
            scheduleStart.addEventListener('change', () => this.syncScheduleRange());
        }
        if (scheduleEnd) {
            scheduleEnd.addEventListener('change', () => this.syncScheduleRange());
        }
        if (slotsPerDayInput) {
            slotsPerDayInput.addEventListener('change', (event) => {
                const value = Number(event.target.value);
                const count = Number.isFinite(value) && value > 0 ? value : 1;
                this.ensureSlotTemplateCount(count);
                event.target.value = count;
            });
        }
        if (addSlotTemplateBtn) {
            addSlotTemplateBtn.addEventListener('click', () => {
                this.addSlotTemplate();
            });
        }
    }

    bindExportControls() {
        const { exportCsvBtn, exportExcelBtn, exportPdfBtn } = this.elements;
        if (exportCsvBtn) {
            exportCsvBtn.addEventListener('click', () => this.exportResultsAsCSV());
        }
        if (exportExcelBtn) {
            exportExcelBtn.addEventListener('click', () => this.exportResultsAsExcel());
        }
        if (exportPdfBtn) {
            exportPdfBtn.addEventListener('click', () => this.exportResultsAsPDF());
        }
    }

    bindNotificationControls() {
        const { dismissNotification, notificationBanner } = this.elements;
        if (dismissNotification) {
            dismissNotification.addEventListener('click', () => this.hideNotification());
        }
        if (notificationBanner) {
            notificationBanner.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    this.hideNotification();
                }
            });
        }
    }

    initializeDefaultSlots() {
        this.state.slotTemplates = [
            this.createSlotTemplate('Morning Slot', '09:00', '12:00'),
            this.createSlotTemplate('Afternoon Slot', '13:00', '16:00')
        ];
        this.renderSlotTemplates();
    }

    createSlotTemplate(label = 'Slot', start = '09:00', end = '12:00') {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : `slot-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            label,
            start,
            end
        };
    }

    renderSlotTemplates() {
        const { slotConfigContainer } = this.elements;
        if (!slotConfigContainer) {
            return;
        }
        slotConfigContainer.innerHTML = '';
        this.state.slotTemplates.forEach(template => {
            const row = document.createElement('div');
            row.className = 'slot-template-row';
            row.dataset.slotId = template.id;
            row.innerHTML = `
                <input type="text" class="field-input slot-label" value="${template.label}" placeholder="Slot label">
                <input type="time" class="field-input slot-start" value="${template.start}">
                <input type="time" class="field-input slot-end" value="${template.end}">
                <button type="button" class="remove-slot-template">Remove</button>
            `;
            const labelInput = row.querySelector('.slot-label');
            const startInput = row.querySelector('.slot-start');
            const endInput = row.querySelector('.slot-end');
            const removeBtn = row.querySelector('.remove-slot-template');
            if (labelInput) {
                labelInput.addEventListener('input', (event) => {
                    template.label = event.target.value || template.label;
                });
            }
            if (startInput) {
                startInput.addEventListener('change', (event) => {
                    template.start = event.target.value || template.start;
                });
            }
            if (endInput) {
                endInput.addEventListener('change', (event) => {
                    template.end = event.target.value || template.end;
                });
            }
            if (removeBtn) {
                removeBtn.addEventListener('click', () => {
                    this.removeSlotTemplate(template.id);
                });
            }
            slotConfigContainer.appendChild(row);
        });
        if (this.elements.slotsPerDayInput) {
            this.elements.slotsPerDayInput.value = String(this.state.slotTemplates.length || 1);
        }
    }

    addSlotTemplate() {
        this.state.slotTemplates.push(this.createSlotTemplate(`Slot ${this.state.slotTemplates.length + 1}`, '09:00', '12:00'));
        this.renderSlotTemplates();
    }

    removeSlotTemplate(templateId) {
        if (this.state.slotTemplates.length <= 1) {
            this.notify('At least one slot template is required.', 'error');
            return;
        }
        this.state.slotTemplates = this.state.slotTemplates.filter(template => template.id !== templateId);
        this.renderSlotTemplates();
    }

    ensureSlotTemplateCount(count) {
        if (!Number.isFinite(count) || count < 1) {
            return;
        }
        const current = this.state.slotTemplates.length;
        if (current === count) {
            return;
        }
        if (current < count) {
            for (let i = current; i < count; i += 1) {
                this.state.slotTemplates.push(this.createSlotTemplate(`Slot ${i + 1}`, '09:00', '12:00'));
            }
        } else {
            this.state.slotTemplates = this.state.slotTemplates.slice(0, count);
        }
        this.renderSlotTemplates();
    }

    syncScheduleRange() {
        const { scheduleStart, scheduleEnd } = this.elements;
        if (!scheduleStart || !scheduleEnd) {
            return;
        }
        const start = scheduleStart.value ? new Date(scheduleStart.value) : null;
        const end = scheduleEnd.value ? new Date(scheduleEnd.value) : null;
        if (start && end && start > end) {
            this.notify('End date cannot be earlier than start date. Please adjust the schedule range.', 'error');
            scheduleEnd.value = '';
        }
    }

    async loadEnrollmentFile(file) {
        try {
            const text = await file.text();
            const parsed = this.parseCSV(text);
            this.applyEnrollmentData(parsed.records);
        } catch (error) {
            this.notify(`Unable to read enrollment file: ${error.message}`, 'error');
        }
    }

    async loadRoomFile(file) {
        try {
            const text = await file.text();
            const parsed = this.parseCSV(text);
            this.applyRoomData(parsed.records);
        } catch (error) {
            this.notify(`Unable to read room file: ${error.message}`, 'error');
        }
    }

    fetchSampleCSV(path) {
        return fetch(path, { cache: 'no-cache' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.text();
            })
            .then(text => this.parseCSV(text));
    }

    parseCSV(text) {
        const rows = [];
        let field = '';
        let inQuotes = false;
        let row = [];
        for (let i = 0; i < text.length; i += 1) {
            const char = text[i];
            if (char === '"') {
                if (inQuotes && text[i + 1] === '"') {
                    field += '"';
                    i += 1;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                row.push(field.trim());
                field = '';
            } else if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && text[i + 1] === '\n') {
                    i += 1;
                }
                row.push(field.trim());
                if (row.some(value => value !== '')) {
                    rows.push(row);
                }
                row = [];
                field = '';
            } else {
                field += char;
            }
        }
        if (field.length || row.length) {
            row.push(field.trim());
            if (row.some(value => value !== '')) {
                rows.push(row);
            }
        }
        if (!rows.length) {
            return { headers: [], records: [] };
        }
        const headers = rows[0].map(header => header.trim());
        const records = rows.slice(1).map(columns => {
            const record = {};
            headers.forEach((header, index) => {
                record[header] = columns[index] !== undefined ? columns[index].trim() : '';
            });
            return record;
        });
        return { headers, records };
    }

    applyEnrollmentData(records) {
        if (!Array.isArray(records) || !records.length) {
            this.notify('No enrollment rows detected in the provided CSV.', 'error');
            return;
        }
        this.state.enrollmentRows = records;
        this.renderPreview(records, this.elements.enrollmentPreview, ['Student Session', 'Student Roll Number', 'Student Name', 'Subject Code', 'Subject Name']);
        this.populateFilterOptions();
        this.updateMetrics();
        this.notify(`Loaded ${records.length} student records.`, 'success');
    }

    applyRoomData(records) {
        if (!Array.isArray(records) || !records.length) {
            this.notify('No room rows detected in the provided CSV.', 'error');
            return;
        }
        const rooms = records.map((record, index) => this.transformRoomRecord(record, index)).filter(Boolean);
        if (!rooms.length) {
            this.notify('Unable to parse room rows. Please verify the CSV format.', 'error');
            return;
        }
        this.state.rooms = rooms;
        const previewRows = rooms.map(room => ({
            'Room ID': room.id,
            'Room Name': room.name,
            'Capacity': room.capacity,
            'Building': room.building,
            'Layout': room.layout
        }));
        this.renderPreview(previewRows, this.elements.roomsPreview, ['Room ID', 'Room Name', 'Capacity', 'Building', 'Layout']);
        this.updateMetrics();
        this.notify(`Loaded ${rooms.length} rooms.`, 'success');
    }

    transformRoomRecord(record, index) {
        const id = record.room_id || record.roomId || record.RoomID || record.RoomId || `ROOM-${index + 1}`;
        const name = record.room_name || record.RoomName || record.name || `Room ${index + 1}`;
        const capacityValue = Number(record.capacity || record.Capacity || record.max_capacity);
        const capacity = Number.isFinite(capacityValue) && capacityValue > 0 ? Math.round(capacityValue) : 0;
        if (!capacity) {
            return null;
        }
        const rowsValue = Number(record.rows || record.Rows);
        const rows = Number.isFinite(rowsValue) && rowsValue > 0 ? Math.round(rowsValue) : Math.max(1, Math.round(Math.sqrt(capacity)));
        let colsPerRowRaw = record.cols_per_row || record['cols_per_row'] || record.columns || '';
        let colsPerRow = [];
        if (typeof colsPerRowRaw === 'string' && colsPerRowRaw.trim()) {
            try {
                colsPerRow = JSON.parse(colsPerRowRaw.replace(/'/g, '"'));
            } catch (error) {
                const cleaned = colsPerRowRaw.replace(/[\[\]]/g, '').split(',').map(value => Number(value.trim())).filter(Number.isFinite);
                if (cleaned.length) {
                    colsPerRow = cleaned;
                }
            }
        }
        if (!Array.isArray(colsPerRow) || !colsPerRow.length) {
            const cols = Math.max(1, Math.ceil(capacity / rows));
            colsPerRow = new Array(rows).fill(cols);
        }
        const building = record.building || record.Building || record.block || '';
        const layout = record.layout || record.Layout || 'grid';
        return {
            id,
            name,
            capacity,
            rows,
            colsPerRow,
            building,
            layout,
            raw: record
        };
    }

    renderPreview(rows, container, preferredOrder = []) {
        if (!container) {
            return;
        }
        if (!rows || !rows.length) {
            container.innerHTML = '<p>No data available.</p>';
            return;
        }
        const maxRows = 5;
        const headers = preferredOrder.length ? preferredOrder.filter(header => Object.prototype.hasOwnProperty.call(rows[0], header)) : Object.keys(rows[0]);
        const previewRows = rows.slice(0, maxRows);
        let html = '<table><thead><tr>';
        headers.forEach(header => {
            html += `<th>${header}</th>`;
        });
        html += '</tr></thead><tbody>';
        previewRows.forEach(row => {
            html += '<tr>';
            headers.forEach(header => {
                html += `<td>${row[header] ?? ''}</td>`;
            });
            html += '</tr>';
        });
        if (rows.length > maxRows) {
            html += `<tr><td colspan="${headers.length}" style="text-align: center; font-style: italic;">... and ${rows.length - maxRows} more rows</td></tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    populateFilterOptions() {
        const { filtersContainer } = this.elements;
        if (!filtersContainer) {
            return;
        }

        const semesterMap = new Map();
        const courseLookup = new Map();

        this.state.enrollmentRows.forEach(row => {
            const session = (row['Student Session'] || '').trim();
            const courseCode = (row['Subject Code'] || '').trim();
            const courseName = (row['Subject Name'] || courseCode).trim();

            if (!session) {
                return;
            }

            if (!semesterMap.has(session)) {
                semesterMap.set(session, {
                    name: session,
                    count: 0,
                    courses: new Map()
                });
            }

            const semesterEntry = semesterMap.get(session);
            semesterEntry.count += 1;

            if (courseCode) {
                if (!semesterEntry.courses.has(courseCode)) {
                    semesterEntry.courses.set(courseCode, {
                        code: courseCode,
                        name: courseName || courseCode,
                        count: 0
                    });
                }
                const courseEntry = semesterEntry.courses.get(courseCode);
                courseEntry.count += 1;
                courseLookup.set(courseCode, {
                    code: courseCode,
                    name: courseEntry.name,
                    count: courseEntry.count,
                    semester: session
                });
            }
        });

        this.state.availableSemesters = Array.from(semesterMap.values()).sort((a, b) => a.name.localeCompare(b.name));
        this.state.availableCoursesBySemester = new Map();
        this.state.courseLookup = courseLookup;
        this.state.selectedSemesters.clear();
        this.state.selectedCourses.clear();

        filtersContainer.innerHTML = '';

        if (!this.state.availableSemesters.length) {
            const empty = document.createElement('p');
            empty.className = 'filters-empty';
            empty.textContent = 'Upload enrollment data to populate semesters and courses.';
            filtersContainer.appendChild(empty);
            this.updateFilterSummaries();
            this.updateFilterNote();
            return;
        }

        const stack = document.createElement('div');
        stack.className = 'filters-stack';

        this.state.availableSemesters.forEach(semester => {
            const courses = Array.from(semester.courses.values()).sort((a, b) => a.code.localeCompare(b.code));
            this.state.availableCoursesBySemester.set(semester.name, courses);

            const card = document.createElement('section');
            card.className = 'filters-semester-card';

            const head = document.createElement('header');
            head.className = 'filters-semester-head';

            const heading = document.createElement('h3');
            heading.textContent = semester.name;

            const meta = document.createElement('span');
            meta.className = 'semester-meta';
            meta.textContent = `${semester.count} student${semester.count !== 1 ? 's' : ''}`;

            head.appendChild(heading);
            head.appendChild(meta);

            const body = document.createElement('div');
            body.className = 'filters-semester-body';

            const semesterCheckboxRow = document.createElement('label');
            semesterCheckboxRow.className = 'filter-item';

            const semesterCheckbox = document.createElement('input');
            semesterCheckbox.type = 'checkbox';
            semesterCheckbox.value = semester.name;
            semesterCheckbox.checked = false;
            semesterCheckbox.dataset.filter = 'semester';

            const semesterInfo = document.createElement('div');
            semesterInfo.className = 'filter-item__body';
            const semesterTitle = document.createElement('div');
            semesterTitle.className = 'filter-item__title';
            semesterTitle.textContent = `Include ${semester.name}`;
            const semesterDesc = document.createElement('div');
            semesterDesc.className = 'filter-item__meta';
            semesterDesc.textContent = 'Toggle to include this semester in scheduling.';

            semesterInfo.appendChild(semesterTitle);
            semesterInfo.appendChild(semesterDesc);
            semesterCheckboxRow.appendChild(semesterCheckbox);
            semesterCheckboxRow.appendChild(semesterInfo);

            const courseList = document.createElement('div');
            courseList.className = 'filters-course-list';

            courses.forEach(course => {
                const courseItem = document.createElement('label');
                courseItem.className = 'filter-item';

                const courseCheckbox = document.createElement('input');
                courseCheckbox.type = 'checkbox';
                courseCheckbox.value = course.code;
                courseCheckbox.disabled = true;
                courseCheckbox.dataset.filter = 'course';
                courseCheckbox.dataset.semester = semester.name;

                const courseInfo = document.createElement('div');
                courseInfo.className = 'filter-item__body';
                const courseTitle = document.createElement('div');
                courseTitle.className = 'filter-item__title';
                courseTitle.textContent = `${course.code} — ${course.name}`;
                const courseMeta = document.createElement('div');
                courseMeta.className = 'filter-item__meta';
                courseMeta.textContent = `${course.count} student${course.count !== 1 ? 's' : ''}`;

                courseInfo.appendChild(courseTitle);
                courseInfo.appendChild(courseMeta);
                courseItem.appendChild(courseCheckbox);
                courseItem.appendChild(courseInfo);
                courseList.appendChild(courseItem);

                courseCheckbox.addEventListener('change', () => {
                    if (courseCheckbox.checked) {
                        this.state.selectedCourses.add(course.code);
                        courseItem.classList.add('filter-item--selected');
                    } else {
                        this.state.selectedCourses.delete(course.code);
                        courseItem.classList.remove('filter-item--selected');
                    }
                    this.updateFilterSummaries();
                    this.updateFilterNote();
                });
            });

            semesterCheckbox.addEventListener('change', () => {
                if (semesterCheckbox.checked) {
                    this.state.selectedSemesters.add(semester.name);
                    semesterCheckboxRow.classList.add('filter-item--selected');
                    courseList.querySelectorAll('input[type="checkbox"]').forEach(input => {
                        input.disabled = false;
                    });
                } else {
                    this.state.selectedSemesters.delete(semester.name);
                    semesterCheckboxRow.classList.remove('filter-item--selected');
                    courseList.querySelectorAll('input[type="checkbox"]').forEach(input => {
                        input.checked = false;
                        input.disabled = true;
                        this.state.selectedCourses.delete(input.value);
                        input.closest('.filter-item')?.classList.remove('filter-item--selected');
                    });
                }
                this.updateFilterSummaries();
                this.updateFilterNote();
            });

            body.appendChild(semesterCheckboxRow);
            if (courses.length) {
                body.appendChild(courseList);
            } else {
                const emptyCourses = document.createElement('div');
                emptyCourses.className = 'filters-empty';
                emptyCourses.textContent = 'No courses found for this semester.';
                body.appendChild(emptyCourses);
            }

            card.appendChild(head);
            card.appendChild(body);
            stack.appendChild(card);
        });

        filtersContainer.appendChild(stack);
        this.updateFilterSummaries();
        this.updateFilterNote();
    }

    updateFilterSummaries() {
        const { semesterSummary, courseSummary } = this.elements;
        if (semesterSummary) {
            const semesters = Array.from(this.state.selectedSemesters);
            semesterSummary.textContent = semesters.length
                ? `Selected: ${semesters.join(', ')}`
                : `All ${this.state.availableSemesters.length} semester${this.state.availableSemesters.length === 1 ? '' : 's'} included`;
        }
        if (courseSummary) {
            const courses = Array.from(this.state.selectedCourses);
            if (courses.length) {
                const labels = courses.map(code => {
                    const lookup = this.state.courseLookup.get(code);
                    return lookup ? `${lookup.code} — ${lookup.name}` : code;
                });
                courseSummary.textContent = `Selected: ${labels.join('; ')}`;
            } else {
                const totalCourses = Array.from(this.state.availableCoursesBySemester.values()).reduce((sum, list) => sum + list.length, 0);
                courseSummary.textContent = `All ${totalCourses} course${totalCourses === 1 ? '' : 's'} included`;
            }
        }
    }

    updateFilterNote() {
        const { filterNote } = this.elements;
        if (!filterNote) {
            return;
        }
        const semesterCount = this.state.selectedSemesters.size;
        const courseCount = this.state.selectedCourses.size;
        if (!semesterCount && !courseCount) {
            filterNote.textContent = 'No filters selected. All courses and semesters will be considered.';
            return;
        }
        const parts = [];
        if (semesterCount) {
            parts.push(`${semesterCount} semester${semesterCount > 1 ? 's' : ''}`);
        }
        if (courseCount) {
            parts.push(`${courseCount} course${courseCount > 1 ? 's' : ''}`);
        }
        filterNote.textContent = `Filters active: ${parts.join(' and ')}. Only matching students will be scheduled.`;
    }

    updateMetrics() {
        const students = this.state.enrollmentRows.length;
        const rooms = this.state.rooms.length;
        const capacity = this.state.rooms.reduce((sum, room) => sum + room.capacity, 0);
        if (this.elements.metricStudents) {
            this.elements.metricStudents.textContent = String(students);
        }
        if (this.elements.metricRooms) {
            this.elements.metricRooms.textContent = String(rooms);
        }
        if (this.elements.metricCapacity) {
            this.elements.metricCapacity.textContent = String(capacity);
        }
        this.updateStepUI();
    }

    canNavigateToStep(targetStep) {
        if (targetStep === this.currentStep) {
            return true;
        }
        if (targetStep < this.currentStep) {
            return true;
        }
        if (targetStep === 2) {
            return this.state.enrollmentRows.length > 0 && this.state.rooms.length > 0;
        }
        if (targetStep === 3) {
            return this.state.enrollmentRows.length > 0 && this.state.rooms.length > 0;
        }
        if (targetStep === 4) {
            return this.state.assignments.length > 0;
        }
        return false;
    }

    handleNextStep(stepIncrement = 1) {
        if (this.currentStep === 4) {
            this.resetToStepOne();
            return;
        }
        let stepsRemaining = stepIncrement;
        while (stepsRemaining > 0) {
            const targetStep = this.currentStep + 1;
            if (targetStep === 2 && !this.validateStep1()) {
                return;
            }
            if (targetStep === 3 && !this.validateStep2()) {
                return;
            }
            if (targetStep === 4) {
                const prepared = this.prepareAssignments();
                if (!prepared) {
                    return;
                }
            }
            this.goToStep(targetStep);
            stepsRemaining -= 1;
            if (this.currentStep === 4) {
                break;
            }
        }
    }

    goToStep(step) {
        if (step < 1 || step > 4) {
            return;
        }
        this.currentStep = step;
        this.updateStepUI();
    }

    updateStepUI() {
        this.elements.stepSections.forEach(section => {
            const sectionStep = Number(section.dataset.step);
            if (sectionStep === this.currentStep) {
                section.classList.add('active');
            } else {
                section.classList.remove('active');
            }
        });
        this.elements.wizardSteps.forEach(step => {
            const stepIndex = Number(step.dataset.step);
            step.classList.toggle('active', stepIndex === this.currentStep);
            step.classList.toggle('completed', stepIndex < this.currentStep && this.canNavigateToStep(stepIndex));
            step.classList.toggle('disabled', stepIndex > this.currentStep && !this.canNavigateToStep(stepIndex));
        });
        if (this.elements.prevBtn) {
            this.elements.prevBtn.disabled = this.currentStep === 1;
        }
        if (this.elements.nextBtn) {
            this.elements.nextBtn.textContent = this.currentStep === 4 ? 'Restart' : 'Next';
        }
        if (this.currentStep === 4) {
            this.elements.resultsCard?.removeAttribute('hidden');
            this.elements.analyticsCard?.removeAttribute('hidden');
        }
    }

    resetToStepOne() {
        this.currentStep = 1;
        this.updateStepUI();
    }

    validateStep1() {
        if (!this.state.enrollmentRows.length) {
            this.notify('Please upload the enrollment CSV before continuing.', 'error');
            return false;
        }
        if (!this.state.rooms.length) {
            this.notify('Please upload the room configuration CSV before continuing.', 'error');
            return false;
        }
        return true;
    }

    validateStep2() {
        if (!this.state.selectedAlgorithm) {
            this.notify('Please pick an allocation strategy before continuing.', 'error');
            return false;
        }
        return true;
    }

    prepareAssignments() {
        if (!this.state.enrollmentRows.length || !this.state.rooms.length) {
            this.notify('Upload both enrollment and room data before generating assignments.', 'error');
            return false;
        }
        const filteredStudents = this.getFilteredStudents();
        if (!filteredStudents.length) {
            this.notify('No students match the current filters. Please adjust your course or semester selection.', 'error');
            return false;
        }
        const slotInstances = this.buildSlotInstances();
        if (!slotInstances.length) {
            this.notify('Unable to derive exam slots. Please double check the schedule configuration.', 'error');
            return false;
        }
        const assignments = this.generateAssignments(filteredStudents, slotInstances);
        if (!assignments.length) {
            this.notify('Unable to allocate students to rooms with the current configuration. Consider increasing max courses per room or adjusting filters.', 'error');
            return false;
        }
        this.state.filteredStudents = filteredStudents;
        this.state.slotInstances = slotInstances;
        this.state.assignments = assignments;
        this.renderResults();
        this.renderAnalytics();
        this.elements.exportCsvBtn?.removeAttribute('disabled');
        this.elements.exportExcelBtn?.removeAttribute('disabled');
        this.elements.exportPdfBtn?.removeAttribute('disabled');
        return true;
    }

    getFilteredStudents() {
        const semesters = this.state.selectedSemesters;
        const courses = this.state.selectedCourses;
        return this.state.enrollmentRows.filter(row => {
            const matchesSemester = !semesters.size || semesters.has(row['Student Session']);
            const matchesCourse = !courses.size || courses.has(row['Subject Code']);
            return matchesSemester && matchesCourse;
        });
    }

    buildSlotInstances() {
        const slots = [];
        const { scheduleStart, scheduleEnd } = this.elements;
        const hasDates = scheduleStart?.value && scheduleEnd?.value;
        let startDate = null;
        let endDate = null;
        if (hasDates) {
            startDate = new Date(scheduleStart.value);
            endDate = new Date(scheduleEnd.value);
        }
        const templates = this.state.slotTemplates.length ? this.state.slotTemplates : [this.createSlotTemplate('Slot 1', '09:00', '12:00')];

        if (hasDates && startDate && endDate && startDate <= endDate) {
            for (let cursor = new Date(startDate); cursor <= endDate; cursor.setDate(cursor.getDate() + 1)) {
                const dateIso = cursor.toISOString().split('T')[0];
                templates.forEach(template => {
                    slots.push({
                        id: `${dateIso}-${template.id}`,
                        date: dateIso,
                        label: template.label,
                        start: template.start,
                        end: template.end
                    });
                });
            }
        } else {
            templates.forEach((template, index) => {
                slots.push({
                    id: `slot-${index + 1}-${template.id}`,
                    date: null,
                    label: template.label,
                    start: template.start,
                    end: template.end
                });
            });
        }
        return slots;
    }

    generateAssignments(students, slotInstances) {
        const rooms = [...this.state.rooms].sort((a, b) => b.capacity - a.capacity);
        const courseBuckets = this.groupStudentsByCourse(students);
        const activeQueue = Object.keys(courseBuckets).filter(code => courseBuckets[code].length);
        const assignments = [];
        if (!activeQueue.length) {
            return assignments;
        }
        const totalSeats = rooms.reduce((sum, room) => sum + room.capacity, 0) * slotInstances.length;
        if (!totalSeats) {
            return assignments;
        }
        slotInstances.forEach(slot => {
            rooms.forEach(room => {
                const roomStudents = [];
                const seenCourses = new Set();
                let idleIterations = 0;
                while (roomStudents.length < room.capacity && activeQueue.length) {
                    const courseCode = activeQueue.shift();
                    const bucket = courseBuckets[courseCode];
                    if (!bucket.length) {
                        idleIterations += 1;
                        if (idleIterations > activeQueue.length + 1) {
                            break;
                        }
                        continue;
                    }
                    if (!seenCourses.has(courseCode) && seenCourses.size >= this.state.maxCoursesPerRoom) {
                        activeQueue.push(courseCode);
                        idleIterations += 1;
                        const reusableCourseExists = activeQueue.some(code => seenCourses.has(code) && courseBuckets[code].length);
                        if (!reusableCourseExists) {
                            break;
                        }
                        continue;
                    }
                    const student = bucket.shift();
                    roomStudents.push(student);
                    seenCourses.add(courseCode);
                    idleIterations = 0;
                    if (bucket.length) {
                        activeQueue.push(courseCode);
                    }
                }
                if (roomStudents.length) {
                    assignments.push({
                        slot,
                        room,
                        students: roomStudents
                    });
                }
            });
        });
        return assignments;
    }

    groupStudentsByCourse(students) {
        const buckets = {};
        students.forEach(student => {
            const course = student['Subject Code'] || 'UNKNOWN';
            if (!buckets[course]) {
                buckets[course] = [];
            }
            buckets[course].push(student);
        });
        // Shuffle each bucket for a more even distribution
        Object.keys(buckets).forEach(course => {
            buckets[course] = this.shuffleArray(buckets[course]);
        });
        return buckets;
    }

    shuffleArray(array) {
        const copy = [...array];
        for (let i = copy.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copy[i], copy[j]] = [copy[j], copy[i]];
        }
        return copy;
    }

    renderResults() {
        const { resultsContainer } = this.elements;
        if (!resultsContainer) {
            return;
        }
        const assignmentsBySlot = this.groupAssignmentsBySlot();
        resultsContainer.innerHTML = '';
        Object.entries(assignmentsBySlot).forEach(([slotId, slotAssignments]) => {
            const slotInfo = slotAssignments[0]?.slot;
            const totalStudents = slotAssignments.reduce((sum, assignment) => sum + assignment.students.length, 0);
            const totalCapacity = slotAssignments.reduce((sum, assignment) => sum + assignment.room.capacity, 0);
            const utilization = totalCapacity ? Math.round((totalStudents / totalCapacity) * 100) : 0;
            const slotHeader = document.createElement('div');
            slotHeader.className = 'slot-summary';
            slotHeader.innerHTML = `
                <div class="slot-summary-header">
                    <div>
                        <h3>${slotInfo?.label ?? 'Slot'} ${slotInfo?.date ? `— ${slotInfo.date}` : ''}</h3>
                        <div class="slot-meta">
                            <span>${slotAssignments.length} room${slotAssignments.length !== 1 ? 's' : ''}</span>
                            <span>${totalStudents} student${totalStudents !== 1 ? 's' : ''}</span>
                            <span class="pill ${utilization >= 85 ? 'pill-success' : utilization < 50 ? 'pill-danger' : ''}">${utilization}% utilization</span>
                        </div>
                    </div>
                    <div class="info-grid">
                        <span>Runs ${slotInfo?.start ?? '??'} – ${slotInfo?.end ?? '??'}</span>
                        ${slotInfo?.date ? `<span>Exam Date: ${slotInfo.date}</span>` : ''}
                    </div>
                </div>
            `;
            const table = document.createElement('table');
            table.innerHTML = `
                <thead>
                    <tr>
                        <th>Room ID</th>
                        <th>Room Name</th>
                        <th>Capacity</th>
                        <th>Students Assigned</th>
                        <th>Slot Used</th>
                        <th>Courses</th>
                        <th>Semesters</th>
                        <th>Utilization</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;
            const tbody = table.querySelector('tbody');
            slotAssignments.forEach(assignment => {
                const courses = Array.from(new Set(assignment.students.map(student => student['Subject Code']))).join(', ');
                const semesters = Array.from(new Set(assignment.students.map(student => student['Student Session']))).join(', ');
                const utilizationPct = assignment.room.capacity ? Math.round((assignment.students.length / assignment.room.capacity) * 100) : 0;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${assignment.room.id}</td>
                    <td>${assignment.room.name}</td>
                    <td>${assignment.room.capacity}</td>
                    <td>${assignment.students.length}</td>
                    <td>${slotInfo?.label ?? 'Slot'}${slotInfo?.date ? ` (${slotInfo.date})` : ''}</td>
                    <td>${courses || '—'}</td>
                    <td>${semesters || '—'}</td>
                    <td>${utilizationPct}%</td>
                `;
                tbody.appendChild(row);
            });
            slotHeader.appendChild(table);
            resultsContainer.appendChild(slotHeader);
        });
    }

    groupAssignmentsBySlot() {
        return this.state.assignments.reduce((accumulator, assignment) => {
            const slotId = assignment.slot.id;
            if (!accumulator[slotId]) {
                accumulator[slotId] = [];
            }
            accumulator[slotId].push(assignment);
            return accumulator;
        }, {});
    }

    formatSlotDate(slot) {
        if (!slot || !slot.date) {
            return 'N/A';
        }
        return slot.date;
    }

    renderAnalytics() {
        const totalStudentsAssigned = this.state.assignments.reduce((sum, assignment) => sum + assignment.students.length, 0);
        const totalCapacity = this.state.assignments.reduce((sum, assignment) => sum + assignment.room.capacity, 0);
        const utilization = totalCapacity ? Math.round((totalStudentsAssigned / totalCapacity) * 100) : 0;
        const unassignedStudents = Math.max(0, this.state.filteredStudents.length - totalStudentsAssigned);
        const roomUtilizations = this.state.assignments.map(assignment => {
            const pct = assignment.room.capacity ? Math.round((assignment.students.length / assignment.room.capacity) * 100) : 0;
            return { room: assignment.room, utilization: pct, students: assignment.students.length };
        });
        const highUtil = roomUtilizations.filter(item => item.utilization >= 85).length;
        const lowUtil = roomUtilizations.filter(item => item.utilization < 50).length;

        if (this.elements.overallUtilization) {
            this.elements.overallUtilization.textContent = `${utilization}%`;
        }
        if (this.elements.unassignedCount) {
            this.elements.unassignedCount.textContent = String(unassignedStudents);
        }
        if (this.elements.highUtilCount) {
            this.elements.highUtilCount.textContent = String(highUtil);
        }
        if (this.elements.lowUtilCount) {
            this.elements.lowUtilCount.textContent = String(lowUtil);
        }
        if (this.elements.aiSummary) {
            const summaryChunks = [
                `Total students placed: ${totalStudentsAssigned}`,
                `Unused students: ${unassignedStudents}`,
                `Average room utilization: ${utilization}%`
            ];
            if (highUtil) {
                summaryChunks.push(`${highUtil} room${highUtil > 1 ? 's' : ''} at or above 85% utilization.`);
            }
            if (lowUtil) {
                summaryChunks.push(`${lowUtil} room${lowUtil > 1 ? 's' : ''} below 50% utilization. Consider rebalancing or merging cohorts.`);
            }
            this.elements.aiSummary.textContent = summaryChunks.join(' ');
        }
        this.renderCharts(roomUtilizations);
    }

    renderCharts(roomUtilizations) {
        const rooms = roomUtilizations.map(item => item.room.name);
        const utilizations = roomUtilizations.map(item => item.utilization);
        const courseTotals = {};
        this.state.assignments.forEach(assignment => {
            assignment.students.forEach(student => {
                const code = student['Subject Code'];
                courseTotals[code] = (courseTotals[code] || 0) + 1;
            });
        });

        if (this.charts.utilization) {
            this.charts.utilization.destroy();
        }
        if (this.elements.utilizationChart) {
            const ctx = this.elements.utilizationChart.getContext('2d');
            this.charts.utilization = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: rooms,
                    datasets: [{
                        label: 'Utilization (%)',
                        data: utilizations,
                        backgroundColor: '#38bdf8'
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }

        if (this.charts.distribution) {
            this.charts.distribution.destroy();
        }
        if (this.elements.distributionChart) {
            const ctx = this.elements.distributionChart.getContext('2d');
            const labels = Object.keys(courseTotals);
            const values = Object.values(courseTotals);
            const colors = labels.map((_, index) => this.generateColor(index));
            this.charts.distribution = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }

    generateColor(index) {
        const palette = [
            '#38bdf8',
            '#818cf8',
            '#f87171',
            '#34d399',
            '#fbbf24',
            '#c084fc',
            '#60a5fa',
            '#f472b6',
            '#bfdbfe',
            '#facc15'
        ];
        return palette[index % palette.length];
    }

    exportResultsAsCSV() {
        if (!this.state.assignments.length) {
            this.notify('Nothing to export yet.', 'info');
            return;
        }
        const headers = [
            'Slot Date',
            'Slot Label',
            'Room ID',
            'Room Name',
            'Capacity',
            'Students Assigned',
            'Courses',
            'Semesters',
            'Utilization (%)'
        ];
        const rows = this.state.assignments.map(assignment => {
            const slot = assignment.slot;
            const courses = Array.from(new Set(assignment.students.map(student => student['Subject Code']))).join('|');
            const semesters = Array.from(new Set(assignment.students.map(student => student['Student Session']))).join('|');
            const utilization = assignment.room.capacity ? Math.round((assignment.students.length / assignment.room.capacity) * 100) : 0;
            return [
                this.formatSlotDate(slot),
                slot.label,
                assignment.room.id,
                assignment.room.name,
                assignment.room.capacity,
                assignment.students.length,
                courses,
                semesters,
                utilization
            ];
        });
        const csvContent = [headers.join(','), ...rows.map(row => row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(','))].join('\n');
        this.downloadBlob(csvContent, 'text/csv', 'room-allocations.csv');
    }

    exportResultsAsExcel() {
        if (typeof XLSX === 'undefined') {
            this.notify('Excel export library is not available.', 'error');
            return;
        }
        if (!this.state.assignments.length) {
            this.notify('Nothing to export yet.', 'info');
            return;
        }
        const rows = this.state.assignments.map(assignment => ({
            SlotDate: this.formatSlotDate(assignment.slot),
            SlotLabel: assignment.slot.label,
            RoomID: assignment.room.id,
            RoomName: assignment.room.name,
            Capacity: assignment.room.capacity,
            StudentsAssigned: assignment.students.length,
            Courses: Array.from(new Set(assignment.students.map(student => student['Subject Code']))).join(', '),
            Semesters: Array.from(new Set(assignment.students.map(student => student['Student Session']))).join(', '),
            Utilization: assignment.room.capacity ? Math.round((assignment.students.length / assignment.room.capacity) * 100) : 0
        }));
        const worksheet = XLSX.utils.json_to_sheet(rows);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Allocations');
        XLSX.writeFile(workbook, 'room-allocations.xlsx');
    }

    exportResultsAsPDF() {
        if (typeof window.jspdf === 'undefined') {
            this.notify('PDF export library is not available.', 'error');
            return;
        }
        if (!this.state.assignments.length) {
            this.notify('Nothing to export yet.', 'info');
            return;
        }
        const doc = new window.jspdf.jsPDF({ orientation: 'landscape' });
        const headers = [['Slot Date', 'Slot Label', 'Room', 'Capacity', 'Students', 'Courses', 'Semesters', 'Utilization']];
        const rows = this.state.assignments.map(assignment => [
            this.formatSlotDate(assignment.slot),
            assignment.slot.label,
            `${assignment.room.id} — ${assignment.room.name}`,
            assignment.room.capacity,
            assignment.students.length,
            Array.from(new Set(assignment.students.map(student => student['Subject Code']))).join(', '),
            Array.from(new Set(assignment.students.map(student => student['Student Session']))).join(', '),
            assignment.room.capacity ? `${Math.round((assignment.students.length / assignment.room.capacity) * 100)}%` : '0%'
        ]);
        doc.text('Room Allocations', 14, 16);
        doc.autoTable({
            head: headers,
            body: rows,
            startY: 22,
            styles: { fontSize: 8 }
        });
        doc.save('room-allocations.pdf');
    }

    downloadBlob(content, mimeType, filename) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    showNotification(message, type = 'info') {
        const { notificationBanner, notificationMessage } = this.elements;
        if (!notificationBanner || !notificationMessage) {
            console.log('[ExamRoomOrchestrator]', message);
            return;
        }
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
            this.notificationTimeout = null;
        }
        notificationBanner.dataset.type = type;
        notificationMessage.textContent = message;
        notificationBanner.hidden = false;
        notificationBanner.focus?.();
        const ttl = type === 'error' ? 8000 : 4000;
        this.notificationTimeout = window.setTimeout(() => this.hideNotification(), ttl);
    }

    hideNotification() {
        const { notificationBanner } = this.elements;
        if (notificationBanner) {
            notificationBanner.hidden = true;
            notificationBanner.removeAttribute('data-type');
        }
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
            this.notificationTimeout = null;
        }
    }

    notify(message, type = 'info') {
        this.showNotification(message, type);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ExamRoomOrchestrator();
});

