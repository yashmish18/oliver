// University Exam Scheduling System - Main Application Logic
class ExamSchedulingSystem {
    constructor() {
        this.currentTab = 'data-import';
        this.enrollmentData = [];
        this.roomsData = [];
        this.selectedAlgorithm = null;
        this.selectedCourses = new Set();
        this.selectedCourseData = new Map();
        this.seatingAssignments = [];
        this.analytics = {};
        
        // Course color mapping
        this.courseColors = [
            '#1FB8CD', '#FFC185', '#B4413C', '#ECEBD5', '#5D878F',
            '#DB4545', '#D2BA4C', '#964325', '#944454', '#13343B'
        ];
        this.courseColorMap = new Map();
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSampleData();
        this.loadSampleRooms();
    }

    bindEvents() {
        // Progress navigation
        document.querySelectorAll('.progress-step').forEach(step => {
            step.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                if (this.canNavigateToTab(tab)) {
                    this.switchTab(tab);
                }
            });
        });

		// Data import events
        document.getElementById('load-sample-data').addEventListener('click', () => {
            this.loadSampleData();
        });
        
		document.getElementById('load-sample-rooms').addEventListener('click', () => {
            this.loadSampleRooms();
        });

		// File uploads
		const enrollmentInput = document.getElementById('enrollment-file');
		if (enrollmentInput) {
			enrollmentInput.addEventListener('change', (e) => {
				const file = e.target.files && e.target.files[0];
				if (file) this.handleEnrollmentUpload(file);
			});
		}

		const roomsInput = document.getElementById('rooms-file');
		if (roomsInput) {
			roomsInput.addEventListener('change', (e) => {
				const file = e.target.files && e.target.files[0];
				if (file) this.handleRoomsUpload(file);
			});
		}
        
        document.getElementById('proceed-to-algorithm').addEventListener('click', () => {
            this.switchTab('algorithm-selection');
        });

        // Algorithm selection events
        document.querySelectorAll('.algorithm-card').forEach(card => {
            card.addEventListener('click', () => {
                this.selectAlgorithm(card.dataset.algorithm);
            });
        });
        
        document.getElementById('back-to-import').addEventListener('click', () => {
            this.switchTab('data-import');
        });
        
        document.getElementById('proceed-to-courses').addEventListener('click', () => {
            this.switchTab('course-selection');
        });

        // Course selection events
        document.getElementById('back-to-algorithm').addEventListener('click', () => {
            this.switchTab('algorithm-selection');
        });
        
        document.getElementById('generate-recommendations').addEventListener('click', () => {
            this.generateRecommendations();
        });

        // Seating visualization events
        document.getElementById('room-selector').addEventListener('change', (e) => {
            this.displayRoomLayout(e.target.value);
        });
        
        document.getElementById('back-to-courses').addEventListener('click', () => {
            this.switchTab('course-selection');
        });
        
        document.getElementById('view-analytics').addEventListener('click', () => {
            this.switchTab('analytics');
        });

        // Analytics events
        document.getElementById('back-to-seating').addEventListener('click', () => {
            this.switchTab('seating-visualization');
        });

        // Export events
        document.getElementById('export-seating').addEventListener('click', () => {
            this.exportSeatingCharts();
        });
        
        document.getElementById('export-analytics').addEventListener('click', () => {
            this.exportAnalytics();
        });
        
        document.getElementById('generate-pdf').addEventListener('click', () => {
            this.generatePDFReport();
        });
    }

    canNavigateToTab(tab) {
        const tabOrder = ['data-import', 'algorithm-selection', 'course-selection', 'seating-visualization', 'analytics'];
        const currentIndex = tabOrder.indexOf(this.currentTab);
        const targetIndex = tabOrder.indexOf(tab);
        
        // Allow going back or moving forward if conditions are met
        if (targetIndex <= currentIndex) return true;
        if (tab === 'algorithm-selection' && this.enrollmentData.length > 0 && this.roomsData.length > 0) return true;
        if (tab === 'course-selection' && this.selectedAlgorithm) return true;
        if (tab === 'seating-visualization' && this.selectedCourses.size > 0) return true;
        if (tab === 'analytics' && this.seatingAssignments.length > 0) return true;
        
        return false;
    }

    switchTab(tabName) {
        console.log('Switching to tab:', tabName);
        
        // Hide all tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
            panel.style.display = 'none';
        });
        
        // Show target tab panel
        const targetPanel = document.getElementById(tabName);
        if (targetPanel) {
            targetPanel.classList.add('active');
            targetPanel.style.display = 'block';
        }
        
        // Update progress navigation
        document.querySelectorAll('.progress-step').forEach(step => {
            step.classList.remove('active', 'completed');
        });
        
        const currentStep = document.querySelector(`[data-tab="${tabName}"]`);
        if (currentStep) {
            currentStep.classList.add('active');
        }
        
        // Mark previous steps as completed
        const tabOrder = ['data-import', 'algorithm-selection', 'course-selection', 'seating-visualization', 'analytics'];
        const currentIndex = tabOrder.indexOf(tabName);
        for (let i = 0; i < currentIndex; i++) {
            const prevStep = document.querySelector(`[data-tab="${tabOrder[i]}"]`);
            if (prevStep) {
                prevStep.classList.add('completed');
            }
        }
        
        this.currentTab = tabName;
        
        // Tab-specific initialization
        if (tabName === 'course-selection') {
            this.initCourseSelection();
        } else if (tabName === 'seating-visualization') {
            this.initSeatingVisualization();
        } else if (tabName === 'analytics') {
            this.initAnalytics();
        }
    }

    loadSampleData() {
        console.log('Loading sample data...');
        
        // Generate realistic sample data
        const coursesBySemester = {
            "SEMESTER 2": [
                {"code": "AS1108", "name": "Applied Physics", "students": 125},
                {"code": "MA1114", "name": "Linear Algebra and Differential Equations", "students": 180},
                {"code": "CS1102", "name": "Programming -II", "students": 165},
                {"code": "DT1101", "name": "Design Thinking", "students": 150},
                {"code": "CT1101", "name": "Critical Thinking and Storytelling", "students": 140}
            ],
            "SEMESTER 4": [
                {"code": "CS2201", "name": "Machine Learning", "students": 95},
                {"code": "CS2105", "name": "Operating Systems", "students": 78},
                {"code": "MG2101", "name": "Managing Business Functions", "students": 88},
                {"code": "CS2103", "name": "Design and Analysis of Algorithms", "students": 82},
                {"code": "CM2101", "name": "Communication and Identity", "students": 92}
            ],
            "SEMESTER 6": [
                {"code": "CS3301", "name": "Minor Project", "students": 75},
                {"code": "CT3101", "name": "Critical Thinking for Decisions", "students": 68},
                {"code": "CS3201", "name": "Theory of Computation", "students": 65},
                {"code": "CS3205", "name": "Big Data Analytics", "students": 45},
                {"code": "CS3207", "name": "Deep Learning", "students": 38}
            ],
            "SEMESTER 8": [
                {"code": "PS4102", "name": "Practice School -II", "students": 55},
                {"code": "CS4201", "name": "Object Oriented Programming", "students": 25},
                {"code": "CS4301", "name": "Software Engineering", "students": 28},
                {"code": "EE4101", "name": "Sustainable Electronic Waste Management", "students": 15}
            ]
        };

        const firstNames = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Rudra", "Prisha", "Ananya", "Fatima", "Anika", "Aadhya", "Kavya", "Aria", "Myra", "Sara", "Zara"];
        const lastNames = ["Sharma", "Patel", "Singh", "Kumar", "Agarwal", "Gupta", "Jain", "Bansal", "Agrawal", "Tiwari", "Mishra", "Yadav", "Saxena", "Verma", "Mehta", "Shah", "Arora", "Malhotra", "Khanna", "Chopra"];
        
        this.enrollmentData = [];
        
        Object.entries(coursesBySemester).forEach(([semester, courses]) => {
            courses.forEach((course, courseIndex) => {
                for (let i = 0; i < course.students; i++) {
                    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
                    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
                    const rollNumber = `BTech${String(courseIndex * 1000 + i + 1).padStart(5, '0')}`;
                    
                    this.enrollmentData.push({
                        "Student Session": semester,
                        "Student Roll Number": rollNumber,
                        "Student Name": `${firstName} ${lastName}`,
                        "Subject Code": course.code,
                        "Subject Name": course.name
                    });
                }
            });
        });
        
        console.log('Generated enrollment data:', this.enrollmentData.length, 'students');
        
        this.displayDataPreview(this.enrollmentData, 'enrollment-preview');
        this.validateData();
    }

    loadSampleRooms() {
        console.log('Loading sample rooms...');
        
        this.roomsData = [
            {
                "room_id": "LT-001",
                "room_name": "Large Theater 1",
                "capacity": 120,
                "layout": "theater",
                "rows": 8,
                "cols_per_row": [12, 14, 14, 16, 16, 16, 14, 12],
                "building": "Academic Block A",
                "max_with_spacing": 40
            },
            {
                "room_id": "AUD-001",
                "room_name": "Main Auditorium", 
                "capacity": 200,
                "layout": "auditorium",
                "rows": 10,
                "cols_per_row": [8, 10, 12, 14, 16, 16, 14, 12, 10, 8],
                "building": "Central Building",
                "max_with_spacing": 67
            },
            {
                "room_id": "CR-101",
                "room_name": "Classroom 101",
                "capacity": 60,
                "layout": "grid", 
                "rows": 6,
                "cols_per_row": [8, 8, 8, 8, 8, 8],
                "building": "Academic Block B",
                "max_with_spacing": 20
            },
            {
                "room_id": "LAB-201",
                "room_name": "Computer Lab 201",
                "capacity": 80,
                "layout": "island",
                "rows": 6, 
                "cols_per_row": [10, 10, 10, 10, 10, 10],
                "building": "IT Building",
                "max_with_spacing": 27
            },
            {
                "room_id": "HALL-001",
                "room_name": "Examination Hall 1",
                "capacity": 150,
                "layout": "grid",
                "rows": 8,
                "cols_per_row": [12, 12, 12, 12, 12, 12, 12, 12],
                "building": "Exam Block", 
                "max_with_spacing": 50
            }
        ];
        
        console.log('Loaded room data:', this.roomsData.length, 'rooms');
        
        this.displayDataPreview(this.roomsData, 'rooms-preview');
        this.validateData();
    }

    displayDataPreview(data, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.classList.remove('hidden');
        
        if (data.length === 0) {
            container.innerHTML = '<p>No data available</p>';
            return;
        }
        
        const headers = Object.keys(data[0]);
        const previewData = data.slice(0, 5);
        
        let html = '<table><thead><tr>';
        headers.forEach(header => {
            html += `<th>${header}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        previewData.forEach(row => {
            html += '<tr>';
            headers.forEach(header => {
                html += `<td>${row[header] || ''}</td>`;
            });
            html += '</tr>';
        });
        
        if (data.length > 5) {
            html += `<tr><td colspan="${headers.length}" style="text-align: center; font-style: italic;">... and ${data.length - 5} more rows</td></tr>`;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    validateData() {
        if (this.enrollmentData.length > 0 && this.roomsData.length > 0) {
            const summary = document.getElementById('validation-summary');
            if (summary) {
                summary.classList.remove('hidden');
                
                const totalStudents = this.enrollmentData.length;
                const totalRooms = this.roomsData.length;
                const totalCapacity = this.roomsData.reduce((sum, room) => sum + room.capacity, 0);
                const uniqueCourses = new Set(this.enrollmentData.map(student => student["Subject Code"])).size;
                
                const statsContainer = summary.querySelector('.validation-stats');
                if (statsContainer) {
                    statsContainer.innerHTML = `
                        <div class="validation-stat">
                            <div class="validation-number">${totalStudents}</div>
                            <div class="validation-label">Total Students</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${uniqueCourses}</div>
                            <div class="validation-label">Unique Courses</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${totalRooms}</div>
                            <div class="validation-label">Available Rooms</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${totalCapacity}</div>
                            <div class="validation-label">Total Capacity</div>
                        </div>
                    `;
                }
            }
            
            const proceedButton = document.getElementById('proceed-to-algorithm');
            if (proceedButton) {
                proceedButton.disabled = false;
            }
        }
    }

    selectAlgorithm(algorithmId) {
        console.log('Selecting algorithm:', algorithmId);
        
        document.querySelectorAll('.algorithm-card').forEach(card => {
            card.classList.remove('selected');
        });
        
        const selectedCard = document.querySelector(`[data-algorithm="${algorithmId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }
        
        const algorithms = {
            ultra_efficient_mixed: {
                name: "Ultra-Efficient Mixed",
                efficiency: "95%",
                description: "Different courses can be adjacent for maximum space utilization",
            },
            conservative_mixed: {
                name: "Conservative Mixed", 
                efficiency: "85%",
                description: "More spacing between different courses for extra security",
            },
            department_spread: {
                name: "Department Spread",
                efficiency: "80%", 
                description: "Ensures even distribution of departments across room",
            },
            anti_cheating_plus: {
                name: "Anti-Cheating Plus",
                efficiency: "75%",
                description: "Maximum security with strategic course separation", 
            },
            balanced_optimization: {
                name: "Balanced Optimization",
                efficiency: "90%",
                description: "Optimal balance between efficiency and security",
            }
        };
        
        this.selectedAlgorithm = {
            id: algorithmId,
            ...algorithms[algorithmId]
        };
        
        const summary = document.getElementById('algorithm-summary');
        if (summary) {
            summary.classList.remove('hidden');
            const nameElement = summary.querySelector('#selected-algorithm-name');
            const descElement = summary.querySelector('#selected-algorithm-description');
            if (nameElement) nameElement.textContent = this.selectedAlgorithm.name;
            if (descElement) descElement.textContent = this.selectedAlgorithm.description;
        }
        
        const proceedButton = document.getElementById('proceed-to-courses');
        if (proceedButton) {
            proceedButton.disabled = false;
        }
    }

    initCourseSelection() {
        console.log('Initializing course selection...');
        
        const coursesBySemester = this.groupCoursesBySemester();
        this.cleanupDynamicSemesterSections();
        
        Object.entries(coursesBySemester).forEach(([semester, courses]) => {
            const slug = this.generateSemesterSlug(semester);
            const container = this.ensureSemesterSection(semester, courses, slug);
            
            if (container && courses.length > 0) {
                container.innerHTML = '';
                courses.forEach((course, index) => {
                    const courseItem = document.createElement('div');
                    courseItem.className = 'course-item';
                    courseItem.dataset.code = course.code;
                    courseItem.dataset.name = course.name;
                    courseItem.dataset.students = String(course.students);
                    courseItem.dataset.semester = semester;
                    courseItem.innerHTML = `
                        <input type="checkbox" id="${course.code}-checkbox" class="course-checkbox" value="${course.code}">
                        <div class="course-info">
                            <div class="course-code">${course.code}</div>
                            <div class="course-name">${course.name}</div>
                            <div class="course-students">${course.students} students</div>
                        </div>
                    `;
                    
                    const checkbox = courseItem.querySelector('.course-checkbox');
                    checkbox.addEventListener('click', (e) => { e.stopPropagation(); });
                    checkbox.addEventListener('change', () => {
                        this.toggleCourseSelection(course.code, course.name, course.students, course.semester || semester);
                    });
                    courseItem.addEventListener('click', (e) => {
                        if (e.target && e.target.classList.contains('course-checkbox')) return;
                        checkbox.checked = !checkbox.checked;
                        this.toggleCourseSelection(course.code, course.name, course.students, course.semester || semester);
                    });
                    
                    container.appendChild(courseItem);
                });
            }
        });
        
        this.updateSelectionSummary();
        // Wire up "Select all" buttons if present
        document.querySelectorAll('[data-select-all]').forEach(btn => {
            if (btn.dataset.bound === 'true') return;
            btn.addEventListener('click', () => {
                const targetId = btn.getAttribute('data-select-all');
                const list = document.getElementById(targetId);
                if (!list) return;
                const items = Array.from(list.querySelectorAll('.course-item'));
                items.forEach(item => {
                    const cb = item.querySelector('.course-checkbox');
                    if (!cb || cb.checked) return;
                    const code = item.dataset.code || '';
                    const name = item.dataset.name || '';
                    const students = parseInt(item.dataset.students || '0', 10) || 0;
                    const sem = item.dataset.semester || '';
                    cb.checked = true;
                    this.toggleCourseSelection(code, name, students, sem);
                });
                this.updateSelectionSummary();
            });
            btn.dataset.bound = 'true';
        });
    }

    groupCoursesBySemester() {
        const grouped = {};
        
        this.enrollmentData.forEach(student => {
            const rawSemester = student["Student Session"] || '';
            const semester = this.normalizeSemester(rawSemester);
            const courseCode = student["Subject Code"];
            const courseName = student["Subject Name"];
            
            if (!grouped[semester]) {
                grouped[semester] = {};
            }
            
            if (!grouped[semester][courseCode]) {
                grouped[semester][courseCode] = {
                    code: courseCode,
                    name: courseName,
                    semester: semester,
                    students: 0
                };
            }

            grouped[semester][courseCode].students++;
        });
        
        // Convert to arrays
        Object.keys(grouped).forEach(semester => {
            grouped[semester] = Object.values(grouped[semester]);
        });
        
        return grouped;
    }

    generateSemesterSlug(semester) {
        return semester.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || `semester-${Math.random().toString(36).slice(2, 7)}`;
    }

    formatSemesterLabel(semester) {
        const trimmed = semester.trim();
        if (!trimmed) return 'Semester';
        return trimmed.replace(/\bsem(ester)?\b/gi, (match) => match.charAt(0).toUpperCase() + match.slice(1).toLowerCase());
    }

    cleanupDynamicSemesterSections() {
        const sectionsWrapper = document.querySelector('.semester-sections');
        if (!sectionsWrapper) return;
        sectionsWrapper.querySelectorAll('[data-dynamic-semester="true"]').forEach(node => node.remove());
    }

    ensureSemesterSection(semester, courses, slug) {
        const sectionsWrapper = document.querySelector('.semester-sections');
        if (!sectionsWrapper) return null;
        const listId = `${slug}-courses`;
        const totalStudents = courses.reduce((sum, course) => sum + (course.students || 0), 0);
        let list = document.getElementById(listId);

        if (!list) {
            const section = document.createElement('div');
            section.className = 'semester-section';
            section.dataset.dynamicSemester = 'true';

            const heading = document.createElement('h3');
            heading.innerHTML = `${this.formatSemesterLabel(semester)} <span class="student-count" id="${slug}-count">(${totalStudents} students)</span>`;

            const controls = document.createElement('div');
            controls.className = 'action-buttons';
            controls.style.margin = '8px 0 12px 0';

            const btn = document.createElement('button');
            btn.className = 'btn btn--outline';
            btn.setAttribute('data-select-all', listId);
            btn.textContent = 'Select all';
            controls.appendChild(btn);

            list = document.createElement('div');
            list.className = 'course-list';
            list.id = listId;

            section.appendChild(heading);
            section.appendChild(controls);
            section.appendChild(list);
            sectionsWrapper.appendChild(section);
        } else {
            const section = list.closest('.semester-section');
            const countEl = section ? section.querySelector('.student-count') : null;
            if (countEl) {
                countEl.textContent = `(${totalStudents} students)`;
            }
        }

        return list;
    }

    normalizeSemester(value) {
        if (!value) return '';
        if (value.includes('-')) {
            const parts = value.split('-');
            const last = parts[parts.length - 1].trim();
            if (last.length > 0) return last.toUpperCase();
        }
        return value.toUpperCase();
    }

    toggleCourseSelection(courseCode, courseName, studentCount, semester = '') {
        const normalizedSemester = this.normalizeSemester(semester);
        console.log('Toggling course selection:', courseCode, studentCount, normalizedSemester);

        const courseData = { code: courseCode, name: courseName, students: studentCount, semester: normalizedSemester };
        
        if (this.selectedCourses.has(courseCode)) {
            this.selectedCourses.delete(courseCode);
            this.selectedCourseData.delete(courseCode);
            this.courseColorMap.delete(courseCode);
        } else {
            this.selectedCourses.add(courseCode);
            this.selectedCourseData.set(courseCode, courseData);
            // Assign color to course
            const colorIndex = this.courseColorMap.size % this.courseColors.length;
            this.courseColorMap.set(courseCode, this.courseColors[colorIndex]);
        }
        
        this.updateSelectionSummary();
    }

    updateSelectionSummary() {
        console.log('Updating selection summary, selected courses:', this.selectedCourses.size);
        
        const summaryContainer = document.getElementById('course-summary');
        const totalStudents = document.getElementById('total-students');
        const roomsNeeded = document.getElementById('rooms-needed');
        const generateButton = document.getElementById('generate-recommendations');
        
        if (!summaryContainer || !totalStudents || !roomsNeeded || !generateButton) return;
        
        if (this.selectedCourses.size === 0) {
            summaryContainer.innerHTML = '<p class="text-secondary">No courses selected</p>';
            totalStudents.textContent = '0';
            roomsNeeded.textContent = '0';
            generateButton.disabled = true;
            return;
        }
        
        let html = '';
        let total = 0;
        
        this.selectedCourses.forEach(courseCode => {
            const courseData = this.selectedCourseData.get(courseCode);
            if (courseData) {
                total += courseData.students;
                html += `
                    <div class="selected-course-item">
                        <span>${courseCode} - ${courseData.name}</span>
                        <span>${courseData.students} students</span>
                    </div>
                `;
            }
        });
        
        summaryContainer.innerHTML = html;
        totalStudents.textContent = total;
        
        // Calculate rooms needed based on algorithm efficiency
        const efficiency = parseInt(this.selectedAlgorithm?.efficiency || '90') / 100;
        const totalCapacity = this.roomsData.reduce((sum, room) => sum + room.max_with_spacing, 0);
        const effectiveCapacity = totalCapacity * efficiency;
        const roomsRequired = Math.ceil(total / effectiveCapacity * this.roomsData.length);
        
        roomsNeeded.textContent = roomsRequired;
        
        generateButton.disabled = false;
        generateButton.style.display = 'inline-flex'; // Ensure button is visible
        
        console.log('Generate button enabled, total students:', total);
    }

    async generateRecommendations() {
        console.log('Generating recommendations with intelligent scheduler...');
        this.showProcessingModal();

        try {
            const schedulingInputs = this.getSchedulingInputs();
            const conflictGraph = this.createCourseConflictGraph();
            const slots = this.buildExamSlots(schedulingInputs);
            const slotAllocation = this.allocateCoursesToSlots(conflictGraph, slots, schedulingInputs);
            const recommendations = this.buildRecommendations(slotAllocation, slots, schedulingInputs);

            this.recommendations = recommendations;
            this.lastSchedulingInputs = schedulingInputs;
            this.lastGeneratedSlots = slots.slice();
            this.switchTab('recommendations');
            this.displayRecommendations(this.recommendations, slots, schedulingInputs);
        } catch (error) {
            console.error('Error generating recommendations:', error);
            alert(`Unable to generate schedule: ${error.message || error}`);
        } finally {
            this.hideProcessingModal();
        }
    }

    createCourseConflictGraph() {
        const courses = Array.from(this.selectedCourseData.values());
        const studentCourses = {};

        this.enrollmentData.forEach(student => {
            const rollNumber = student["Student Roll Number"];
            const courseCode = student["Subject Code"];
            if (this.selectedCourses.has(courseCode)) {
                if (!studentCourses[rollNumber]) {
                    studentCourses[rollNumber] = [];
                }
                studentCourses[rollNumber].push(courseCode);
            }
        });

        const conflictGraph = new Map();
        courses.forEach(course => conflictGraph.set(course.code, new Set()));

        for (const student in studentCourses) {
            const enrolledCourses = studentCourses[student];
            for (let i = 0; i < enrolledCourses.length; i++) {
                for (let j = i + 1; j < enrolledCourses.length; j++) {
                    conflictGraph.get(enrolledCourses[i]).add(enrolledCourses[j]);
                    conflictGraph.get(enrolledCourses[j]).add(enrolledCourses[i]);
                }
            }
        }

        return conflictGraph;
    }

    getSchedulingInputs() {
        const parseDate = (inputId, fallback = null) => {
            const input = document.getElementById(inputId);
            if (!input || !input.value) {
                return fallback ? new Date(fallback) : null;
            }
            const dt = new Date(input.value);
            return isNaN(dt.getTime()) ? (fallback ? new Date(fallback) : null) : dt;
        };

        const startDate = parseDate('exam-start-date', new Date());
        let endDate = parseDate('exam-end-date', null);

        if (endDate && endDate < startDate) {
            endDate = new Date(startDate);
        }

        const slotsInput = document.getElementById('exam-slots');
        let slotsPerDay = parseInt(slotsInput ? slotsInput.value : '2', 10);
        if (!Number.isFinite(slotsPerDay) || slotsPerDay <= 0) {
            slotsPerDay = 2;
        }

        const slotDurationInput = document.getElementById('slot-duration');
        let slotDurationHours = parseFloat(slotDurationInput ? slotDurationInput.value : '2');
        if (!Number.isFinite(slotDurationHours) || slotDurationHours <= 0) {
            slotDurationHours = 2;
        }

        const efficiency = Math.max(0.5, Math.min(1, parseInt(this.selectedAlgorithm?.efficiency || '90', 10) / 100));
        const totalEffectiveCapacity = this.roomsData.reduce((sum, room) => sum + this.getEffectiveRoomCapacity(room, efficiency), 0);

        return {
            startDate,
            endDate,
            slotsPerDay,
            slotDurationHours,
            algorithmEfficiency: efficiency,
            totalEffectiveCapacity: Math.max(1, totalEffectiveCapacity)
        };
    }

    buildExamSlots(inputs) {
        const slots = [];
        const msPerDay = 24 * 60 * 60 * 1000;
        const { startDate, endDate, slotsPerDay } = inputs;

        let totalSlots = slotsPerDay;
        if (endDate && !isNaN(endDate.getTime())) {
            const days = Math.max(0, Math.round((endDate.getTime() - startDate.getTime()) / msPerDay)) + 1;
            totalSlots = Math.max(slotsPerDay, days * slotsPerDay);
        }

        for (let sequence = 1; sequence <= totalSlots; sequence++) {
            slots.push(this.createSlotFromSequence(sequence, inputs));
        }

        return slots;
    }

    createSlotFromSequence(sequence, inputs) {
        const { startDate, slotsPerDay, endDate } = inputs;
        const slotIndex = (sequence - 1) % slotsPerDay;
        const dayOffset = Math.floor((sequence - 1) / slotsPerDay);
        const date = new Date(startDate);
        date.setDate(startDate.getDate() + dayOffset);
        const outsideWindow = endDate ? date > endDate : false;

        return {
            id: `slot-${sequence}`,
            sequence,
            date,
            slotIndex,
            outsideWindow
        };
    }

    createOverflowSlot(existingSlots, inputs) {
        const sequence = existingSlots.length > 0 ? existingSlots[existingSlots.length - 1].sequence + 1 : 1;
        const slot = this.createSlotFromSequence(sequence, inputs);
        existingSlots.push(slot);
        return slot;
    }

    allocateCoursesToSlots(conflictGraph, slots, inputs) {
        const courseEntries = Array.from(this.selectedCourseData.values());
        if (courseEntries.length === 0) {
            throw new Error('No courses selected for scheduling.');
        }

        const slotUsage = new Map();
        const slotById = new Map(slots.map(slot => [slot.id, slot]));
        const assignments = new Map();
        const semesterLastSequence = new Map();

        const orderedCourses = courseEntries.sort((a, b) => {
            const degreeA = (conflictGraph.get(a.code) || new Set()).size;
            const degreeB = (conflictGraph.get(b.code) || new Set()).size;
            if (degreeA !== degreeB) return degreeB - degreeA;
            if (a.students !== b.students) return b.students - a.students;
            return a.code.localeCompare(b.code);
        });

        orderedCourses.forEach(course => {
            const conflicts = conflictGraph.get(course.code) || new Set();
            const blockedSlots = new Set();
            const blockedDayIndices = new Set();
            conflicts.forEach(conflictCourse => {
                const assigned = assignments.get(conflictCourse);
                if (assigned) {
                    blockedSlots.add(assigned.slotId);
                    const assignedSlot = slotById.get(assigned.slotId);
                    if (assignedSlot) {
                        const dayIndex = Math.floor((assignedSlot.sequence - 1) / inputs.slotsPerDay);
                        blockedDayIndices.add(dayIndex);
                    }
                }
            });

            let candidateSlots = slots.filter(slot => {
                if (blockedSlots.has(slot.id)) return false;
                const dayIndex = Math.floor((slot.sequence - 1) / inputs.slotsPerDay);
                if (blockedDayIndices.has(dayIndex)) return false;
                return true;
            });
            if (candidateSlots.length === 0) {
                const overflowSlot = this.createOverflowSlot(slots, inputs);
                slotById.set(overflowSlot.id, overflowSlot);
                candidateSlots = [overflowSlot];
            }

            candidateSlots.sort((a, b) => {
                const scoreA = this.evaluateSlotScore(a, course, slotUsage, semesterLastSequence, inputs);
                const scoreB = this.evaluateSlotScore(b, course, slotUsage, semesterLastSequence, inputs);
                return scoreA - scoreB;
            });

            const chosenSlot = candidateSlots[0];
            assignments.set(course.code, { slotId: chosenSlot.id });

            if (!slotUsage.has(chosenSlot.id)) {
                slotUsage.set(chosenSlot.id, {
                    totalStudents: 0,
                    courses: new Set(),
                    semesterLoad: new Map()
                });
            }

            const usage = slotUsage.get(chosenSlot.id);
            usage.totalStudents += course.students;
            usage.courses.add(course.code);
            const semesterKey = course.semester || 'UNKNOWN';
            usage.semesterLoad.set(
                semesterKey,
                (usage.semesterLoad.get(semesterKey) || 0) + 1
            );

            semesterLastSequence.set(semesterKey, chosenSlot.sequence);
        });

        return {
            assignments,
            slotUsage,
            slotById
        };
    }

    evaluateSlotScore(slot, course, slotUsage, semesterLastSequence, inputs) {
        const usage = slotUsage.get(slot.id);
        const loadRatio = usage ? usage.totalStudents / inputs.totalEffectiveCapacity : 0;
        const semesterKey = course.semester || 'UNKNOWN';
        const sameSemesterCount = usage ? (usage.semesterLoad.get(semesterKey) || 0) : 0;

        const lastSequence = semesterLastSequence.get(semesterKey);
        const spacingPenalty = lastSequence ? Math.max(0, 3 - (slot.sequence - lastSequence)) : 0;
        const outsidePenalty = slot.outsideWindow ? 5 : 0;
        const daySpreadPenalty = slot.sequence * 0.02;

        return (loadRatio * 4) + (sameSemesterCount * 2) + spacingPenalty + outsidePenalty + daySpreadPenalty;
    }

    getEffectiveRoomCapacity(room, efficiency) {
        const base = Number.isFinite(room.max_with_spacing) && room.max_with_spacing > 0 ? room.max_with_spacing : room.capacity || 0;
        return Math.max(0, Math.floor(base * efficiency));
    }

    buildRecommendations(slotAllocation, slots, inputs) {
        const { assignments } = slotAllocation;
        const courseMap = this.selectedCourseData;
        const slotCourses = new Map();
        const sortedSlots = slots.slice().sort((a, b) => a.sequence - b.sequence);

        assignments.forEach(({ slotId }, courseCode) => {
            if (!slotCourses.has(slotId)) {
                slotCourses.set(slotId, []);
            }
            const course = courseMap.get(courseCode);
            if (course) {
                slotCourses.get(slotId).push({
                    ...course
                });
            }
        });

        const recommendations = [];

        for (let i = 0; i < sortedSlots.length; i++) {
            const slot = sortedSlots[i];
            const coursesInSlot = (slotCourses.get(slot.id) || []).map(course => ({
                ...course
            }));
            if (coursesInSlot.length === 0) continue;

            const allocation = this.allocateRoomsForSlot(coursesInSlot, inputs);

            const slotRecommendation = {
                slotId: slot.id,
                slotSequence: slot.sequence,
                date: slot.date,
                slotIndex: slot.slotIndex,
                outsideWindow: slot.outsideWindow,
                rooms: allocation.roomPlans,
                courses: Array.from(allocation.courseSummaries.values()),
                overflow: allocation.overflowCourses.length > 0
            };
            recommendations.push(slotRecommendation);

            if (allocation.roomPlans.length === 0 && allocation.overflowCourses.length > 0) {
                console.warn('No seating capacity available for slot', slot.slotSequence);
                continue;
            }

            if (allocation.overflowCourses.length > 0) {
                const overflowSlot = this.createOverflowSlot(slots, inputs);
                const nextCourses = allocation.overflowCourses.map(item => ({
                    ...item.course,
                    students: item.remaining
                }));
                slotCourses.set(overflowSlot.id, (slotCourses.get(overflowSlot.id) || []).concat(nextCourses));
                sortedSlots.push(overflowSlot);
            }
        }

        return recommendations.sort((a, b) => a.slotSequence - b.slotSequence);
    }

    allocateRoomsForSlot(coursesInSlot, inputs) {
        const roomStates = this.roomsData
            .map(room => {
                const effective = this.getEffectiveRoomCapacity(room, inputs.algorithmEfficiency);
                return {
                    room,
                    capacity: effective,
                    remaining: effective,
                    allocations: [],
                    _allocationMap: new Map()
                };
            })
            .filter(state => state.capacity > 0)
            .sort((a, b) => b.capacity - a.capacity);

        const courseStates = coursesInSlot.map(course => ({
            course,
            remaining: course.students
        }));

        const courseSummaries = new Map();

        roomStates.forEach(roomState => {
            if (courseStates.every(cs => cs.remaining <= 0)) {
                return;
            }

            while (roomState.remaining > 0) {
                const activeCourses = courseStates
                    .filter(cs => cs.remaining > 0)
                    .sort((a, b) => b.remaining - a.remaining);

                if (activeCourses.length === 0) break;

                const share = Math.max(1, Math.ceil(roomState.remaining / activeCourses.length));

                for (let idx = 0; idx < activeCourses.length && roomState.remaining > 0; idx++) {
                    const courseState = activeCourses[idx];
                    if (courseState.remaining <= 0) continue;

                    const maxAssignable = Math.min(courseState.remaining, roomState.remaining);
                    if (maxAssignable <= 0) continue;

                    const allocation = idx === activeCourses.length - 1
                        ? maxAssignable
                        : Math.min(maxAssignable, share);

                    if (allocation <= 0) continue;

                    if (!roomState._allocationMap.has(courseState.course.code)) {
                        const allocationEntry = { course: courseState.course, students: 0 };
                        roomState._allocationMap.set(courseState.course.code, allocationEntry);
                        roomState.allocations.push(allocationEntry);
                    }
                    const allocationEntry = roomState._allocationMap.get(courseState.course.code);
                    allocationEntry.students += allocation;

                    roomState.remaining -= allocation;
                    courseState.remaining -= allocation;

                    if (!courseSummaries.has(courseState.course.code)) {
                        courseSummaries.set(courseState.course.code, {
                            course: courseState.course,
                            totalAssigned: 0,
                            rooms: []
                        });
                    }

                    const summary = courseSummaries.get(courseState.course.code);
                    summary.totalAssigned += allocation;
                    let roomRecord = summary.rooms.find(r => (r.room.room_id || r.room.room_name) === (roomState.room.room_id || roomState.room.room_name));
                    if (!roomRecord) {
                        roomRecord = { room: roomState.room, students: 0 };
                        summary.rooms.push(roomRecord);
                    }
                    roomRecord.students += allocation;
                }

                if (activeCourses.every(cs => cs.remaining <= 0)) break;
                if (roomState.remaining <= 0) break;

                // Prevent infinite loop when share is larger than remaining single course
                const remainingActive = courseStates.filter(cs => cs.remaining > 0);
                if (remainingActive.length === 1) {
                    const courseState = remainingActive[0];
                    const allocation = Math.min(courseState.remaining, roomState.remaining);
                    if (allocation <= 0) break;

                    if (!roomState._allocationMap.has(courseState.course.code)) {
                        const allocationEntry = { course: courseState.course, students: 0 };
                        roomState._allocationMap.set(courseState.course.code, allocationEntry);
                        roomState.allocations.push(allocationEntry);
                    }
                    const allocationEntry = roomState._allocationMap.get(courseState.course.code);
                    allocationEntry.students += allocation;

                    roomState.remaining -= allocation;
                    courseState.remaining -= allocation;

                    if (!courseSummaries.has(courseState.course.code)) {
                        courseSummaries.set(courseState.course.code, {
                            course: courseState.course,
                            totalAssigned: 0,
                            rooms: []
                        });
                    }

                    const summary = courseSummaries.get(courseState.course.code);
                    summary.totalAssigned += allocation;
                    let roomRecord = summary.rooms.find(r => (r.room.room_id || r.room.room_name) === (roomState.room.room_id || roomState.room.room_name));
                    if (!roomRecord) {
                        roomRecord = { room: roomState.room, students: 0 };
                        summary.rooms.push(roomRecord);
                    }
                    roomRecord.students += allocation;
                    break;
                }
            }

            roomState.allocations.sort((a, b) => b.students - a.students);
        });

        const roomPlans = roomStates
            .filter(state => state.allocations.length > 0)
            .map(state => ({
                room: state.room,
                plannedCapacity: state.capacity,
                assigned: state.capacity - state.remaining,
                remaining: state.remaining,
                allocations: state.allocations
            }));

        const overflowCourses = courseStates
            .filter(cs => cs.remaining > 0)
            .map(cs => ({
                course: cs.course,
                remaining: cs.remaining
            }));

        courseSummaries.forEach(summary => {
            summary.rooms.sort((a, b) => b.students - a.students);
        });

        return {
            roomPlans,
            courseSummaries,
            overflowCourses
        };
    }

    formatSlotLabel(rec, inputs) {
        const dateText = rec.date ? rec.date.toLocaleDateString() : 'TBD';
        const timeText = this.formatTimeWindow(rec.slotIndex, inputs.slotDurationHours || 2);
        const dayIndex = Math.floor((rec.slotSequence - 1) / inputs.slotsPerDay) + 1;
        const slotText = `Day ${dayIndex}, Slot ${rec.slotIndex + 1}`;
        return `${dateText} • ${timeText} (${slotText})`;
    }

    formatTimeWindow(slotIndex, durationHours) {
        const baseHour = 9; // 9 AM default start
        const duration = Math.max(1, durationHours);
        const start = baseHour + (slotIndex * duration);
        const end = start + duration;

        const toTime = (value) => {
            const hours = Math.floor(value);
            const minutes = Math.round((value - hours) * 60);
            const date = new Date(0, 0, 0, hours, minutes, 0);
            return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
        };

        return `${toTime(start)} - ${toTime(end)}`;
    }


	// Parse CSV text into array of objects using first row as headers
	parseCSV(text) {
		const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim().length > 0);
		if (lines.length === 0) return [];
		const headers = lines[0].split(',').map(h => h.trim());
		const rows = [];
		for (let i = 1; i < lines.length; i++) {
			const cols = [];
			let current = '';
			let inQuotes = false;
			for (let j = 0; j < lines[i].length; j++) {
				const ch = lines[i][j];
				if (ch === '"') {
					// handle escaped quotes
					if (inQuotes && lines[i][j + 1] === '"') { current += '"'; j++; }
					else { inQuotes = !inQuotes; }
				} else if (ch === ',' && !inQuotes) {
					cols.push(current);
					current = '';
				} else {
					current += ch;
				}
			}
			cols.push(current);
			const obj = {};
			headers.forEach((h, idx) => { obj[h] = (cols[idx] || '').trim(); });
			rows.push(obj);
		}
		return rows;
	}

	// File upload handlers
	handleEnrollmentUpload(file) {
		const reader = new FileReader();
		reader.onload = () => {
			const raw = String(reader.result || '');
			const rows = this.parseCSV(raw);
			// Expect headers: Student Session, Student Roll Number, Student Name, Subject Code, Subject Name
			this.enrollmentData = rows.map(r => ({
				"Student Session": r['Student Session'] || r['semester'] || r['Semester'] || '',
				"Student Roll Number": r['Student Roll Number'] || r['Roll Number'] || r['roll'] || '',
				"Student Name": r['Student Name'] || r['Name'] || '',
				"Subject Code": r['Subject Code'] || r['Course Code'] || r['code'] || '',
				"Subject Name": r['Subject Name'] || r['Course Name'] || r['name'] || ''
			})).filter(r => r["Subject Code"]);
			this.displayDataPreview(this.enrollmentData, 'enrollment-preview');
			this.validateData();
		};
		reader.onerror = () => { console.error('Failed to read enrollment file'); };
		reader.readAsText(file);
	}

	handleRoomsUpload(file) {
		const reader = new FileReader();
		reader.onload = () => {
			const raw = String(reader.result || '');
			const rows = this.parseCSV(raw);
			// Map common room CSV headers into expected structure
			const normalizeKey = (key) => String(key || '').trim().toLowerCase().replace(/^\ufeff/, '');
			const none = (v) => {
				const s = String(v ?? '').trim();
				return s.length === 0 || s.toLowerCase() === 'none' ? '' : s;
			};
			const toInt = (v, d = 0) => {
				const n = parseInt(String(v ?? '').trim(), 10);
				return Number.isFinite(n) ? n : d;
			};
			const parseCols = (v) => {
				const s = none(v);
				if (!s) return [];
				try {
					// Try JSON array: "[10, 10]"
					const arr = JSON.parse(s);
					return Array.isArray(arr) ? arr.map(x => toInt(x, 0)) : [];
				} catch (_) {
					return [];
				}
			};
			this.roomsData = rows.map(r => {
				const normalized = {};
				Object.keys(r).forEach(key => {
					const cleanKey = normalizeKey(key);
					if (cleanKey.length === 0) return;
					normalized[cleanKey] = r[key];
				});
				const capacity = toInt(normalized['capacity'] || normalized['cap'] || 0, 0);
				const rawEff = normalized['max_with_spacing'] || normalized['max with spacing'] || normalized['effective_capacity'] || normalized['effective'] || '';
				const effParsed = toInt(rawEff, 0);
				const maxWithSpacing = effParsed > 0 ? effParsed : Math.floor(capacity * 0.33);
				const layoutRaw = none(normalized['layout']);
				return {
					room_id: none(normalized['room_id'] || normalized['id'] || normalized['room']),
					room_name: none(normalized['room_name'] || normalized['name'] || normalized['room']),
					capacity: capacity,
					layout: layoutRaw || 'grid',
					rows: toInt(normalized['rows'] || 0, 0),
					cols_per_row: parseCols(normalized['cols_per_row'] || normalized['cols per row']),
					building: none(normalized['building']),
					max_with_spacing: Math.max(0, maxWithSpacing)
				};
			}).filter(r => (r.room_id || r.room_name) && r.capacity > 0);
			this.displayDataPreview(this.roomsData, 'rooms-preview');
			this.validateData();
		};
		reader.onerror = () => { console.error('Failed to read rooms file'); };
		reader.readAsText(file);
	}


    displayRecommendations(recommendations, slots, inputs) {
        const recommendationsContainer = document.getElementById('recommendations-content');
        if (!recommendationsContainer) return;

        let html = '<h3>AI-Assisted Exam Schedule</h3>';

        if (recommendations.length === 0) {
            html += '<p>No schedule could be generated with the current selection. Please review course selection and room capacity.</p>';
            recommendationsContainer.innerHTML = html;
            return;
        }

        const uniqueCourses = new Set();
        let totalStudentsScheduled = 0;
        let totalRoomsUsed = 0;
        let overflowSlots = 0;

        recommendations.forEach(slot => {
            slot.courses.forEach(courseSummary => {
                uniqueCourses.add(courseSummary.course.code);
                totalStudentsScheduled += courseSummary.totalAssigned;
            });
            totalRoomsUsed += slot.rooms.length;
            if (slot.overflow) overflowSlots += 1;
        });

        const outsideWindow = recommendations.filter(rec => rec.outsideWindow).length;

        html += `
            <div class="schedule-overview">
                <div class="overview-item">
                    <span class="overview-label">Unique Courses Scheduled</span>
                    <span class="overview-value">${uniqueCourses.size}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Time Slots Used</span>
                    <span class="overview-value">${recommendations.length}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Rooms Utilized</span>
                    <span class="overview-value">${totalRoomsUsed}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Students Placed</span>
                    <span class="overview-value">${totalStudentsScheduled}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Overflow Slots Added</span>
                    <span class="overview-value">${overflowSlots}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Outside Preferred Window</span>
                    <span class="overview-value ${outsideWindow > 0 ? 'text-warning' : ''}">${outsideWindow}</span>
                </div>
            </div>
        `;

        // Callout about mixing policy
        html += `
            <div class="card card--info" style="margin: 12px 0;">
                <div><strong>Note</strong>: Rooms are intentionally mixed — multiple courses and semesters share the same room to optimize capacity.</div>
            </div>
        `;

        const courseRows = [];
        recommendations.forEach(slot => {
            slot.courses.forEach(courseSummary => {
                if (!courseSummary || courseSummary.totalAssigned <= 0) return;
                const rooms = courseSummary.rooms.slice().sort((a, b) => b.students - a.students);
                const primaryRoom = rooms[0] ? rooms[0].room : null;
                const overflowRooms = rooms.slice(1);
                courseRows.push({
                    course: courseSummary.course,
                    students: courseSummary.totalAssigned,
                    slot,
                    primaryRoom,
                    overflowRooms,
                    rooms
                });
            });
        });

        courseRows.sort((a, b) => {
            if (a.slot.slotSequence !== b.slot.slotSequence) {
                return a.slot.slotSequence - b.slot.slotSequence;
            }
            return a.course.code.localeCompare(b.course.code);
        });

        html += `
            <div class="legacy-table-block">
                <h4>Course Schedule Summary</h4>
                <table class="schedule-table">
                    <thead>
                        <tr>
                            <th>Course</th>
                            <th>Students</th>
                            <th>Exam Date & Time</th>
                            <th>Primary Room</th>
                            <th>Additional Rooms</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        courseRows.forEach(row => {
            const altRooms = row.overflowRooms.map(entry => `${entry.room.room_name} (${entry.students})`).join(', ') || 'None';
            const primaryName = row.primaryRoom ? `${row.primaryRoom.room_name}` : 'Assigned via overflow';
            const noteParts = [];
            if (row.overflowRooms.length > 0) {
                noteParts.push('Distributed across multiple rooms to satisfy capacity and mixing requirements');
            }
            if (row.slot.outsideWindow) {
                noteParts.push('Scheduled outside selected date window');
            }
            const note = noteParts.length > 0 ? noteParts.join(' • ') : 'Standard placement';

            html += `
                <tr>
                    <td>${row.course.code} - ${row.course.name}</td>
                    <td>${row.students}</td>
                    <td>${this.formatSlotLabel(row.slot, inputs)}</td>
                    <td>${primaryName}</td>
                    <td>${altRooms}</td>
                    <td>${note}</td>
                </tr>
            `;
        });

        if (courseRows.length === 0) {
            html += `
                <tr>
                    <td colspan="6" class="text-secondary">No courses were scheduled.</td>
                </tr>
            `;
        }

        html += `
                    </tbody>
                </table>
            </div>
        `;

        recommendations.forEach(slot => {
            const slotLabel = this.formatSlotLabel(slot, inputs);
            const totalInSlot = slot.courses.reduce((sum, c) => sum + c.totalAssigned, 0);
            html += `
                <div class="slot-block">
                    <div class="slot-header">
                        <h4>${slotLabel}</h4>
                        <div class="slot-meta">
                            <span>${slot.rooms.length} room(s)</span>
                            <span>${totalInSlot} students</span>
                            <span>Slot ${slot.slotSequence}</span>
                        </div>
                        ${slot.outsideWindow ? '<p class="text-warning">⚠ Scheduled outside selected date range</p>' : ''}
                        ${slot.overflow ? '<p class="text-warning">Unplaced students were automatically moved to an extra slot.</p>' : ''}
                    </div>
                    <div class="slot-body">
                        <div class="room-grid">
            `;

            slot.rooms.forEach(roomPlan => {
                const allocations = roomPlan.allocations.slice().sort((a, b) => a.course.code.localeCompare(b.course.code));
                const roomUtil = roomPlan.plannedCapacity > 0 ? Math.round((roomPlan.assigned / roomPlan.plannedCapacity) * 100) : 0;
                html += `
                    <div class="room-card">
                        <div class="room-card__header">
                            <h5>${roomPlan.room.room_name}</h5>
                            <span>${roomPlan.assigned}/${roomPlan.plannedCapacity} seats • ${roomUtil}% utilization</span>
                        </div>
                        <table class="room-allocation-table">
                            <thead>
                                <tr>
                                    <th>Course (Semester)</th>
                                    <th>Students</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                allocations.forEach(allocation => {
                    html += `
                        <tr>
                            <td>${allocation.course.code} - ${allocation.course.name} <span class="text-secondary">(${allocation.course.semester || 'N/A'})</span></td>
                            <td>${allocation.students}</td>
                        </tr>
                    `;
                });

                if (roomPlan.remaining > 0) {
                    html += `
                        <tr class="room-remaining">
                            <td colspan="2">${roomPlan.remaining} seats left available for contingency.</td>
                        </tr>
                    `;
                }

                html += `
                            </tbody>
                        </table>
                    </div>
                    <hr class="room-separator" />
                `;
            });

            html += `
                        </div>
                        <div class="course-summary">
                            <h5>Course Coverage</h5>
                            <table class="course-allocation-table">
                                <thead>
                                    <tr>
                                        <th>Course</th>
                                        <th>Semester</th>
                                        <th>Students</th>
                                        <th>Rooms Utilized</th>
                                    </tr>
                                </thead>
                                <tbody>
            `;

            const sortedCourses = slot.courses.slice().sort((a, b) => a.course.code.localeCompare(b.course.code));
            sortedCourses.forEach(courseSummary => {
                const roomNames = courseSummary.rooms.map(r => `${r.room.room_name} (${r.students})`).join(', ');
                html += `
                    <tr>
                        <td>${courseSummary.course.code} - ${courseSummary.course.name}</td>
                        <td>${courseSummary.course.semester || 'N/A'}</td>
                        <td>${courseSummary.totalAssigned}</td>
                        <td>${roomNames}</td>
                    </tr>
                `;
            });

            html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        });

        recommendationsContainer.innerHTML = html;

        this.calculateAnalytics(inputs);
        this.renderRecommendationsAnalytics(inputs);
    }

	// Render analytics UI inside the recommendations tab
    renderRecommendationsAnalytics(inputs = null) {
        const container = document.getElementById('recommendations-analytics');
        if (!container) return;

        const stats = this.analytics || { totalExams: 0, totalRoomsUsed: 0, overallEfficiency: 0, roomBreakdown: [], totalStudents: 0 };
        const schedulingInputs = inputs || this.lastSchedulingInputs || this.getSchedulingInputs();

        container.innerHTML = `
            <div class="analytics-dashboard">
                <h3>Analytics</h3>
                <div class="stats-grid" style="margin-top: 12px;">
                    <div class="stat-item"><div class="stat-number">${stats.totalStudents}</div><div class="stat-label">Students Scheduled</div></div>
                    <div class="stat-item"><div class="stat-number">${stats.totalExams}</div><div class="stat-label">Exam Sessions</div></div>
                    <div class="stat-item"><div class="stat-number">${stats.totalRoomsUsed}</div><div class="stat-label">Rooms Utilized</div></div>
                    <div class="stat-item"><div class="stat-number">${stats.overallEfficiency}%</div><div class="stat-label">Seat Efficiency</div></div>
                </div>
                <div class="analytics-grid" style="margin-top: 16px;">
                    <div class="analytics-card">
                        <h3>Room Utilization</h3>
                        <div class="chart-container" style="position: relative; height: 260px;">
                            <canvas id="reco-utilization-chart"></canvas>
                        </div>
                    </div>
                    <div class="analytics-card">
                        <h3>Slot Distribution</h3>
                        <div class="chart-container" style="position: relative; height: 260px;">
                            <canvas id="reco-distribution-chart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const utilCanvas = document.getElementById('reco-utilization-chart');
        if (utilCanvas) {
            const ctx = utilCanvas.getContext('2d');
            const roomData = (this.analytics.roomBreakdown || []).filter(b => b.room);
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: roomData.map(r => r.room.room_name),
                    datasets: [{
                        label: 'Avg Utilization (%)',
                        data: roomData.map(r => r.utilization),
                        backgroundColor: '#1FB8CD',
                        borderColor: '#1FB8CD',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true, max: 100 } },
                    plugins: { legend: { display: false } }
                }
            });
        }

        const distCanvas = document.getElementById('reco-distribution-chart');
        if (distCanvas) {
            const ctx = distCanvas.getContext('2d');
            const courseDistribution = {};
            (this.recommendations || []).forEach(rec => {
                const key = `Slot ${rec.slotSequence}`;
                courseDistribution[key] = (courseDistribution[key] || 0) + rec.courses.length;
            });
            const labels = Object.keys(courseDistribution);
            const data = Object.values(courseDistribution);
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor: this.courseColors,
                        borderColor: this.courseColors,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }
    }

    showProcessingModal() {
        const modal = document.getElementById('processing-modal');
        if (modal) {
            modal.classList.remove('hidden');
            
            const progress = document.getElementById('processing-progress');
            const stats = document.getElementById('processing-stats');
            
            let progressValue = 0;
            const interval = setInterval(() => {
                progressValue += Math.random() * 15;
                if (progressValue > 100) progressValue = 100;
                
                if (progress) progress.style.width = `${progressValue}%`;
                
                if (stats) {
                    if (progressValue < 30) {
                        stats.textContent = 'Analyzing course distribution...';
                    } else if (progressValue < 60) {
                        stats.textContent = 'Optimizing room assignments...';
                    } else if (progressValue < 90) {
                        stats.textContent = 'Applying anti-cheating algorithms...';
                    } else {
                        stats.textContent = 'Finalizing seating arrangements...';
                        clearInterval(interval);
                    }
                }
            }, 200);
            
            this.processingInterval = interval;
        }
    }

    hideProcessingModal() {
        const modal = document.getElementById('processing-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
        }
    }

    async simulateSeatingGeneration(schedule) {
        return new Promise((resolve) => {
            setTimeout(() => {
                this.generateRoomAssignments(schedule);
                resolve();
            }, 3000);
        });
    }

    generateRoomAssignments(schedule) {
        console.log('Generating room assignments...');
        
        this.seatingAssignments = [];

        schedule.forEach(item => {
            if (!item.room) return;

            const students = this.enrollmentData.filter(student => 
                student["Subject Code"] === item.course.code
            );

            const rooms = [item.room, ...item.overflowRooms];
            let studentIndex = 0;

		rooms.forEach(room => {
                if (studentIndex >= students.length) return;

                const roomAssignment = {
                    room: room,
                    students: [],
                    seats: this.generateRoomSeats(room)
                };

                const seatsToFill = Math.min(room.capacity, students.length - studentIndex);

				for (let i = 0; i < seatsToFill; i++) {
                    const student = students[studentIndex + i];
                    let seat = this.findOptimalSeat(roomAssignment.seats, student["Subject Code"], new Set(roomAssignment.seats.filter(s => s.occupied).map(s => s.id)));
                    if (seat) {
                        seat.student = student;
                        seat.occupied = true;
                        seat.courseCode = student["Subject Code"];
                        roomAssignment.students.push(student);
                    }
                }

				// Apply a quick simulated annealing pass to reduce adjacent same-course neighbors
				this.improveSeatingWithSimulatedAnnealing(roomAssignment.seats, 200);
                studentIndex += seatsToFill;
                this.seatingAssignments.push(roomAssignment);
            });
        });
        
        console.log('Generated seating assignments:', this.seatingAssignments.length);
    }

	// Simulated annealing to minimize adjacent same-course pairs
	improveSeatingWithSimulatedAnnealing(seats, iterations) {
		const occupied = seats.filter(s => s.occupied);
		if (occupied.length < 2) return;
		const score = () => {
			let conflicts = 0;
			for (const s of occupied) {
				const adj = this.getAdjacentSeats(seats, s);
				conflicts += adj.filter(a => a.occupied && a.courseCode === s.courseCode).length;
			}
			return conflicts;
		};
		let currentScore = score();
		let temperature = 1.0;
		for (let it = 0; it < iterations; it++) {
			temperature *= 0.98;
			const i = Math.floor(Math.random() * occupied.length);
			const j = Math.floor(Math.random() * occupied.length);
			if (i === j) continue;
			const a = occupied[i];
			const b = occupied[j];
			// swap students
			const tmpStudent = a.student, tmpCode = a.courseCode;
			a.student = b.student; a.courseCode = b.courseCode;
			b.student = tmpStudent; b.courseCode = tmpCode;
			const newScore = score();
			const delta = newScore - currentScore;
			if (delta <= 0 || Math.random() < Math.exp(-delta / Math.max(0.001, temperature))) {
				currentScore = newScore;
			} else {
				// revert
				const tmpStudent2 = a.student, tmpCode2 = a.courseCode;
				a.student = b.student; a.courseCode = b.courseCode;
				b.student = tmpStudent2; b.courseCode = tmpCode2;
			}
		}
	}

    generateRoomSeats(room) {
        const seats = [];
        const rowLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        
        // Dynamically calculate a balanced layout
        const capacity = room.capacity;
        const numRows = Math.ceil(Math.sqrt(capacity * 0.8));
        const numCols = Math.ceil(capacity / numRows);

        for (let row = 0; row < numRows; row++) {
            for (let col = 0; col < numCols; col++) {
                if (seats.length < capacity) {
                    seats.push({
                        id: `${rowLabels[row]}${col + 1}`,
                        row: row,
                        col: col,
                        occupied: false,
                        student: null,
                        courseCode: null
                    });
                }
            }
        }
        
        return seats;
    }

    findOptimalSeat(seats, courseCode, usedSeats) {
        const availableSeats = seats.filter(seat => !usedSeats.has(seat.id));
        
        // 1. Prioritize seats with no adjacent students of the same course
        for (const seat of availableSeats) {
            const adjacentSeats = this.getAdjacentSeats(seats, seat);
            const hasAdjacentSameCourse = adjacentSeats.some(adj => 
                adj.occupied && adj.courseCode === courseCode
            );
            if (!hasAdjacentSameCourse) {
                return seat;
            }
        }
        
        // 2. If not found, prioritize seats with no adjacent students at all
        for (const seat of availableSeats) {
            const adjacentSeats = this.getAdjacentSeats(seats, seat);
            const hasAdjacentStudents = adjacentSeats.some(adj => adj.occupied);
            if (!hasAdjacentStudents) {
                return seat;
            }
        }

        // 3. If still not found, return the first available seat
        return availableSeats[0] || null;
    }

    getAdjacentSeats(seats, targetSeat) {
        const adjacent = [];
        const { row, col } = targetSeat;
        
        // Check 8 directions (including diagonals)
        const directions = [
            [-1, -1], [-1, 0], [-1, 1],
            [0, -1],           [0, 1],
            [1, -1],  [1, 0],  [1, 1]
        ];
        
        directions.forEach(([dRow, dCol]) => {
            const adjRow = row + dRow;
            const adjCol = col + dCol;
            const adjSeat = seats.find(s => s.row === adjRow && s.col === adjCol);
            if (adjSeat) {
                adjacent.push(adjSeat);
            }
        });
        
        return adjacent;
    }

    shuffleArray(array) {
        const shuffled = [...array];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }

    initSeatingVisualization() {
        console.log('Initializing seating visualization...');
        console.log('Seating assignments:', this.seatingAssignments.length);
        
        const roomSelector = document.getElementById('room-selector');
        if (roomSelector) {
            roomSelector.innerHTML = '<option value="">Select Room</option>';
            
            this.seatingAssignments.forEach((assignment, index) => {
                if (assignment.students.length > 0) {
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = `${assignment.room.room_name} (${assignment.students.length} students)`;
                    roomSelector.appendChild(option);
                }
            });
            
            if (this.seatingAssignments.length > 0 && this.seatingAssignments[0].students.length > 0) {
                roomSelector.value = '0';
                this.displayRoomLayout('0');
            }
        }
        
        this.createCourseLegend();
    }

    createCourseLegend() {
        const legendContainer = document.getElementById('course-legend');
        if (legendContainer) {
            legendContainer.innerHTML = '';
            
            this.courseColorMap.forEach((color, courseCode) => {
                const legendItem = document.createElement('div');
                legendItem.className = 'legend-item';
                legendItem.innerHTML = `
                    <div class="legend-color" style="background-color: ${color}"></div>
                    <span>${courseCode}</span>
                `;
                legendContainer.appendChild(legendItem);
            });
        }
    }

    displayRoomLayout(roomIndex) {
        console.log('Displaying room layout for index:', roomIndex);
        
        if (roomIndex === '') return;
        
        const assignment = this.seatingAssignments[parseInt(roomIndex)];
        if (!assignment) return;
        
        const layoutContainer = document.getElementById('room-layout');
        
        // Update room info
        const capacityEl = document.getElementById('room-capacity');
        const occupiedEl = document.getElementById('room-occupied');
        const utilizationEl = document.getElementById('room-utilization');
        
        if (capacityEl) capacityEl.textContent = assignment.room.capacity;
        if (occupiedEl) occupiedEl.textContent = assignment.students.length;
        if (utilizationEl) {
            utilizationEl.textContent = Math.round((assignment.students.length / assignment.room.max_with_spacing) * 100) + '%';
        }
        
        // Generate room layout
        if (layoutContainer) {
            layoutContainer.innerHTML = this.generateRoomHTML(assignment);
            this.addSeatInteractivity();
        }
    }

    generateRoomHTML(assignment) {
        const { room, seats } = assignment;
        const rowLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        
        let html = '<div class="room-grid">';
        let currentRow = -1;

        seats.forEach(seat => {
            if (seat.row !== currentRow) {
                if (currentRow !== -1) {
                    html += '</div>'; // Close previous row
                }
                currentRow = seat.row;
                html += '<div class="room-row">';
                html += `<div class="room-row-label">${rowLabels[currentRow]}</div>`;
            }

            const seatClass = seat.occupied ? 'seat occupied' : 'seat';
            const bgColor = seat.occupied ? this.courseColorMap.get(seat.courseCode) : '';
            
            html += `
                <div class="${seatClass}" 
                     data-seat-id="${seat.id}"
                     data-student='${seat.student ? JSON.stringify(seat.student) : ''}'
                     data-course="${seat.courseCode}"
                     style="${bgColor ? `background-color: ${bgColor}; color: white;` : ''}">
                    ${seat.id}
                </div>
            `;
        });

        if (seats.length > 0) {
            html += '</div>'; // Close the last row
        }
        
        html += '</div>';
        return html;
    }

    addSeatInteractivity() {
        const tooltip = document.getElementById('student-tooltip');
        
        document.querySelectorAll('.seat').forEach(seat => {
            seat.addEventListener('mouseenter', (e) => {
                const studentData = e.target.dataset.student;
                if (studentData && tooltip) {
                    const student = JSON.parse(studentData);
                    const seatId = e.target.dataset.seatId;
                    
                    const nameEl = tooltip.querySelector('.student-name');
                    const rollEl = tooltip.querySelector('.student-roll');
                    const courseEl = tooltip.querySelector('.student-course');
                    const positionEl = tooltip.querySelector('.seat-position');
                    
                    if (nameEl) nameEl.textContent = student["Student Name"];
                    if (rollEl) rollEl.textContent = `Roll: ${student["Student Roll Number"]}`;
                    if (courseEl) courseEl.textContent = `Course: ${student["Subject Code"]} - ${student["Subject Name"]}`;
                    if (positionEl) positionEl.textContent = `Seat: ${seatId}`;
                    
                    tooltip.classList.remove('hidden');
                    this.positionTooltip(tooltip, e);
                }
            });
            
            seat.addEventListener('mouseleave', () => {
                if (tooltip) tooltip.classList.add('hidden');
            });
            
            seat.addEventListener('mousemove', (e) => {
                if (tooltip && !tooltip.classList.contains('hidden')) {
                    this.positionTooltip(tooltip, e);
                }
            });
        });
    }

    positionTooltip(tooltip, event) {
        const rect = tooltip.offsetParent.getBoundingClientRect();
        const x = event.clientX - rect.left + 10;
        const y = event.clientY - rect.top - tooltip.offsetHeight - 10;
        
        tooltip.style.left = `${Math.max(0, Math.min(x, rect.width - tooltip.offsetWidth))}px`;
        tooltip.style.top = `${Math.max(0, y)}px`;
    }

    initAnalytics() {
        console.log('Initializing analytics...');
        const inputs = this.lastSchedulingInputs || this.getSchedulingInputs();
        this.calculateAnalytics(inputs);
        this.updateAnalyticsDisplay();
        
        // Delay chart creation to ensure DOM is ready
        setTimeout(() => {
            this.createCharts();
        }, 100);
    }

    calculateAnalytics(inputs = null) {
        const schedulingInputs = inputs || this.lastSchedulingInputs || this.getSchedulingInputs();
        const recommendations = this.recommendations || [];
        const roomsUsed = new Set();

        let totalStudents = 0;
        let totalAssignedSeats = 0;
        let totalEffectiveCapacity = 0;
        let totalCourseSessions = 0;

        const roomBreakdownMap = new Map();

        recommendations.forEach(slot => {
            slot.courses.forEach(courseSummary => {
                totalStudents += courseSummary.totalAssigned;
                totalCourseSessions += 1;
            });

            slot.rooms.forEach(roomPlan => {
                const room = roomPlan.room;
                const roomKey = room.room_id || room.room_name;
                roomsUsed.add(roomKey);
                totalAssignedSeats += roomPlan.assigned;
                totalEffectiveCapacity += roomPlan.plannedCapacity;

                if (!roomBreakdownMap.has(roomKey)) {
                    roomBreakdownMap.set(roomKey, {
                        room,
                        totalStudents: 0,
                        sessions: 0,
                        capacity: 0
                    });
                }

                const record = roomBreakdownMap.get(roomKey);
                record.totalStudents += roomPlan.assigned;
                record.sessions += 1;
                record.capacity += roomPlan.plannedCapacity;
            });
        });

        const overallEfficiency = totalEffectiveCapacity > 0
            ? Math.round((totalAssignedSeats / totalEffectiveCapacity) * 100)
            : 0;

        const roomBreakdown = Array.from(roomBreakdownMap.values()).map(record => {
            const utilization = record.capacity > 0
                ? Math.round((record.totalStudents / record.capacity) * 100)
                : 0;
            return {
                room: record.room,
                totalStudents: record.totalStudents,
                sessions: record.sessions,
                utilization: Math.min(100, Math.max(0, utilization))
            };
        }).sort((a, b) => b.utilization - a.utilization);

        this.analytics = {
            totalExams: totalCourseSessions,
            totalRoomsUsed: roomsUsed.size,
            overallEfficiency,
            totalStudents,
            roomBreakdown
        };

        console.log('Analytics calculated:', this.analytics);
    }

    updateAnalyticsDisplay() {
        const elements = {
            students: document.getElementById('analytics-students'),
            rooms: document.getElementById('analytics-rooms'),
            efficiency: document.getElementById('analytics-efficiency'),
            courses: document.getElementById('analytics-courses'),
        };

        if (elements.students) elements.students.textContent = this.analytics.totalStudents || 0;
        if (elements.rooms) elements.rooms.textContent = this.analytics.totalRoomsUsed;
        if (elements.efficiency) elements.efficiency.textContent = this.analytics.overallEfficiency + '%';
        if (elements.courses) elements.courses.textContent = this.selectedCourses.size;

        this.updateRoomBreakdown();
    }

    updateRoomBreakdown() {
        const container = document.getElementById('room-breakdown');
        if (!container) return;

        const breakdown = this.analytics?.roomBreakdown || [];

        if (breakdown.length === 0) {
            container.innerHTML = '<p class="text-secondary">Room utilization insights will appear after generating a schedule.</p>';
            return;
        }

        let html = '';
        breakdown.forEach(record => {
            html += `
                <div class="room-breakdown-item">
                    <div class="room-header">
                        <span class="room-name">${record.room.room_name}</span>
                        <span class="room-utilization">${record.utilization}% average utilization</span>
                    </div>
                    <div class="room-details">
                        <span>Sessions: ${record.sessions}</span>
                        <span>Students Assigned: ${record.totalStudents}</span>
                        <span>Effective Capacity: ${this.getEffectiveRoomCapacity(record.room, this.lastSchedulingInputs?.algorithmEfficiency || 0.9)}</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    createCharts() {
        this.createUtilizationChart();
        this.createDistributionChart();
    }

    createUtilizationChart() {
        const canvas = document.getElementById('utilization-chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const roomData = this.analytics.roomBreakdown.filter(b => b.room);
        const labels = roomData.map(r => r.room.room_name);
        const data = roomData.map(r => r.utilization);

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Room Utilization (%)',
                    data: data,
                    backgroundColor: '#1FB8CD',
                    borderColor: '#1FB8CD',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    createDistributionChart() {
        const canvas = document.getElementById('distribution-chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const courseDistribution = {};
        const recommendations = this.recommendations || [];
        recommendations.forEach(rec => {
            const slot = rec.slotSequence;
            if (!courseDistribution[slot]) {
                courseDistribution[slot] = 0;
            }
            courseDistribution[slot] += rec.courses.length;
        });

        const labels = Object.keys(courseDistribution).map(slot => `Slot ${slot}`);
        const data = Object.values(courseDistribution);

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: this.courseColors,
                    borderColor: this.courseColors,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    exportSeatingCharts() {
        const data = this.seatingAssignments.map(assignment => ({
            room: assignment.room.room_name,
            students: assignment.students.map(student => ({
                name: student["Student Name"],
                rollNumber: student["Student Roll Number"],
                course: student["Subject Code"],
                seat: assignment.seats.find(seat => seat.student === student)?.id || 'N/A'
            }))
        }));
        
        this.downloadJSON(data, 'seating-arrangements.json');
    }

    exportAnalytics() {
        const analyticsData = {
            summary: this.analytics,
            algorithm: this.selectedAlgorithm,
            roomDetails: this.analytics.roomBreakdown,
            timestamp: new Date().toISOString()
        };
        
        this.downloadJSON(analyticsData, 'analytics-report.json');
    }

    generatePDFReport() {
        // Simulate PDF generation
        alert('PDF report generation would be implemented with a PDF library like jsPDF. Report includes:\n\n- Seating arrangements by room\n- Student allocation details\n- Efficiency metrics\n- Algorithm comparison\n- Room utilization charts');
    }

    downloadJSON(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing application...');
    new ExamSchedulingSystem();
});